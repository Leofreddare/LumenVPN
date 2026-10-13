"""Authenticated TLS relay transport plus loopback SOCKS5 TCP/UDP."""
import asyncio
import hashlib
import hmac
import json
import socket
import ssl
import struct
from dataclasses import dataclass, replace
from hardware import detect

from profile_types import Profile

async def choose_endpoint(profile,addresses,delay=.25,options=None):
    """Race validated TLS probes before installing routes; cancel every loser."""
    unique=list(dict.fromkeys(addresses));v4=[ip for ip in unique if ':' not in ip];v6=[ip for ip in unique if ':' in ip]
    ordered=[]
    while v4 or v6:
        if v4:ordered.append(v4.pop(0))
        if v6:ordered.append(v6.pop(0))
    if not ordered:raise ValueError('Server hostname has no addresses.')
    async def check(ip):
        tunnel=Tunnel(replace(profile,host=ip),options=options) if options else Tunnel(replace(profile,host=ip));await tunnel.probe(full=True)
        return ip,tunnel
    # Stagger slow attempts, but advance immediately after a definite failure.
    # This avoids paying the full stagger for refused/unreachable endpoints.
    addresses=iter(ordered[:8]);tasks=[];pending=set();errors=[];loop=asyncio.get_running_loop();next_at=0.;remaining=True
    def launch():
        nonlocal next_at,remaining
        try:ip=next(addresses)
        except StopIteration:remaining=False;return
        task=asyncio.create_task(check(ip));tasks.append(task);pending.add(task);next_at=loop.time()+max(0,delay)
    launch()
    try:
        while pending:
            timeout=max(0,next_at-loop.time()) if remaining else None
            done,_=await asyncio.wait(pending,timeout=timeout,return_when=asyncio.FIRST_COMPLETED)
            if not done:launch();continue
            pending.difference_update(done)
            for task in done:
                try:return task.result()
                except Exception as error:errors.append(error)
            if remaining:launch()
        raise next((e for e in errors if isinstance(e,ValueError)),errors[0])
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)

async def relay_streams(left_reader,left_writer,right_reader,right_writer,on_data=None,idle_timeout=300,chunk_size=65536):
    """Backpressured streams with one shared idle timer, including one-way traffic."""
    loop=asyncio.get_running_loop();activity=[loop.time()];blocked=[None,None]
    async def pump(source,destination,direction):
        index=0 if direction=='up' else 1
        while data:=await source.read(chunk_size):
            destination.write(data);blocked[index]=loop.time();await destination.drain();blocked[index]=None;activity[0]=loop.time()
            if on_data:on_data(direction,len(data))
    async def idle():
        while True:
            remaining=min(idle_timeout-(loop.time()-start) for start in [activity[0],*(x for x in blocked if x is not None)])
            if remaining<=0:raise asyncio.TimeoutError('Tunnel stream is idle.')
            await asyncio.sleep(min(30,remaining))
    jobs=[asyncio.create_task(pump(left_reader,right_writer,'up')),asyncio.create_task(pump(right_reader,left_writer,'down')),asyncio.create_task(idle())]
    try:
        done,_=await asyncio.wait(jobs,return_when=asyncio.FIRST_COMPLETED)
        for task in done:task.result()
        if jobs[0] in done and jobs[1] not in done:
            # TLS has no write_eof: retain the existing downstream grace period.
            done,_=await asyncio.wait(jobs[1:],return_when=asyncio.FIRST_COMPLETED)
            for task in done:task.result()
    finally:
        for task in jobs:task.cancel()
        await asyncio.gather(*jobs,return_exceptions=True)

class UDPAssociation(asyncio.DatagramProtocol):
    def __init__(self, expected_port=0,budget=None):
        self.transport=None;self.peer=None;self.expected_port=expected_port
        self.queue=asyncio.Queue(maxsize=128);self.queued_bytes=0;self.budget=budget if budget is not None else [0]
    def connection_made(self,transport): self.transport=transport
    def datagram_received(self,data,addr):
        if addr[0]!='127.0.0.1' or len(data)<7 or len(data)>65535 or data[:3]!=b'\0\0\0':return
        if self.expected_port and addr[1]!=self.expected_port:return
        if self.peer is None:self.peer=addr
        if addr!=self.peer:return
        if self.queued_bytes+len(data)>262144 or self.budget[0]+len(data)>1048576:return
        try:self.queue.put_nowait(data);self.queued_bytes+=len(data);self.budget[0]+=len(data)
        except asyncio.QueueFull:pass

    def release(self,size):self.queued_bytes-=size;self.budget[0]-=size
    def clear(self):
        while not self.queue.empty():self.release(len(self.queue.get_nowait()))

class Tunnel:
    def __init__(self,profile,options=None):
        self.options=options or {};self.profile=profile;self.pin=profile.validate();self.server=None;self.tasks=set()
        self.upload=self.download=self.connections=self.failures=0
        self.closed=False;self.capabilities=[];self.udp_budget=[0]
        self.warm=[];self.preparing=set();self.warm_timer=None
        self.warm_limit=2;self.warm_lifetime=20
        self.warm_retry=0
        self.hardware=detect()
        self.context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.context.check_hostname=False;self.context.verify_mode=ssl.CERT_NONE
        self.context.minimum_version=ssl.TLSVersion.TLSv1_3
    async def open_tls(self):
        reader,writer=await asyncio.wait_for(asyncio.open_connection(self.profile.host,self.profile.port,ssl=self.context,
            server_hostname=self.profile.host,ssl_handshake_timeout=self.options.get('dial_timeout',10),ssl_shutdown_timeout=3,limit=self.hardware.chunk),self.options.get('dial_timeout',15))
        try:
            cert=writer.get_extra_info('ssl_object').getpeercert(binary_form=True)
            if not hmac.compare_digest(hashlib.sha256(cert).hexdigest(),self.pin):
                raise ValueError('Server identity changed. Import a fresh file from your trusted panel.')
            writer.transport.set_write_buffer_limits(high=self.hardware.chunk,low=self.hardware.chunk//4)
            return reader,writer
        except BaseException:
            writer.close();raise
    async def request(self,reader,writer,action,host=None,port=None):
        try:
            request=dict(v=1,token=self.profile.token,action=action)
            if action=="connect" and "padding-v1" in self.capabilities:request["padding"]=True
            if host is not None:request.update(host=host,port=port)
            writer.write(json.dumps(request,separators=(',',':')).encode()+b'\n');await writer.drain()
            line=await asyncio.wait_for(reader.readuntil(b'\n'),self.options.get('request_timeout',15))
            if len(line)>1024:raise ValueError('Invalid relay response.')
            reply=json.loads(line)
            if reply.get('ok') is not True:raise ValueError('Relay rejected the connection. Check pairing and allowed ports.')
            if action=='ping':self.capabilities=reply.get('capabilities',[])
            if request.get("padding"):
                from padding import PaddingReader,PaddingWriter
                return PaddingReader(reader),PaddingWriter(writer)
            return reader,writer
        except BaseException:
            writer.close();raise
    def expire_warm(self):
        if self.warm_timer:self.warm_timer.cancel();self.warm_timer=None
        now=asyncio.get_running_loop().time();ready=[]
        for created,reader,writer in self.warm:
            if now-created>=self.warm_lifetime or reader.at_eof() or writer.is_closing():writer.close()
            else:ready.append((created,reader,writer))
        self.warm=ready
        if ready:
            delay=max(0,ready[0][0]+self.warm_lifetime-now)
            self.warm_timer=asyncio.get_running_loop().call_later(delay,self.expire_warm)
    def fill_warm(self):
        # Fill only on startup/demand. Idle expiry never sends keepalives or refills.
        if self.closed or self.server is None or 'warm' not in self.capabilities or asyncio.get_running_loop().time()<self.warm_retry:return
        async def prepare():
            writer=None
            try:
                reader,writer=await self.open_tls()
                await self.request(reader,writer,'warm')
                if self.closed:writer.close();return
                self.warm.append((asyncio.get_running_loop().time(),reader,writer))
                self.expire_warm();writer=None
            except Exception:
                # Avoid amplifying server overload with speculative handshakes.
                self.warm_retry=asyncio.get_running_loop().time()+5
            finally:
                if writer:writer.close()
        for _ in range(max(0,self.warm_limit-len(self.warm)-len(self.preparing))):
            task=asyncio.create_task(prepare());self.preparing.add(task);task.add_done_callback(self.preparing.discard)
    async def remote(self,action,host=None,port=None):
        if self.closed:raise ConnectionError('Tunnel stopped.')
        if action in ('connect','udp'):
            self.expire_warm()
            if self.warm:
                _,reader,writer=self.warm.pop();self.expire_warm();self.fill_warm()
                try:return await self.request(reader,writer,action,host,port)
                except (OSError,asyncio.IncompleteReadError):
                    # No application bytes have been sent: a stale prepared link
                    # may safely be replaced, retaining pin/auth checks.
                    pass
            self.fill_warm()
        reader,writer=await self.open_tls()
        return await self.request(reader,writer,action,host,port)
    async def probe(self,full=False):
        _,writer=await self.remote('ping');writer.close();await writer.wait_closed()
        if full and not {'tcp','udp','ipv6','all-ports'}.issubset(self.capabilities):
            raise ValueError('Update your server to Lumen 2 and remove ALLOWED_PORTS restrictions before using Windows mode.')
    async def start(self):
        self.server=await asyncio.start_server(self.handle,'127.0.0.1',self.profile.local_port,limit=self.hardware.chunk)
        self.fill_warm()
    async def stop(self):
        self.closed=True
        if self.warm_timer:self.warm_timer.cancel();self.warm_timer=None
        for _,_,writer in self.warm:writer.close()
        self.warm.clear()
        if self.server:self.server.close()
        jobs=list(self.tasks|self.preparing)
        for task in jobs:task.cancel()
        if jobs:await asyncio.gather(*jobs,return_exceptions=True)
        if self.server:await self.server.wait_closed()
    async def udp(self,reader,writer,expected_port):
        remote_reader,remote_writer=await self.remote('udp')
        transport=None; jobs=[]
        try:
            protocol=UDPAssociation(expected_port,self.udp_budget)
            transport,_=await asyncio.get_running_loop().create_datagram_endpoint(lambda:protocol,local_addr=('127.0.0.1',0))
            bound=transport.get_extra_info('sockname')
            writer.write(b'\x05\x00\x00\x01'+socket.inet_aton('127.0.0.1')+struct.pack('!H',bound[1]));await writer.drain()
            async def send():
                while True:
                    data=await protocol.queue.get();protocol.release(len(data))
                    parts=[struct.pack('!I',len(data)),data];size=len(data);count=1
                    # Drain only packets already ready; no timer or coalescing wait.
                    while count<32 and size<65536:
                        try:data=protocol.queue.get_nowait()
                        except asyncio.QueueEmpty:break
                        protocol.release(len(data));parts.extend((struct.pack('!I',len(data)),data));size+=len(data);count+=1
                    remote_writer.writelines(parts);await remote_writer.drain();self.upload+=size
            async def receive():
                while True:
                    size=struct.unpack('!I',await remote_reader.readexactly(4))[0]
                    if not 7<=size<=65535:raise ValueError('Invalid UDP frame.')
                    data=await remote_reader.readexactly(size)
                    if protocol.peer and transport.get_write_buffer_size()<=262144:transport.sendto(data,protocol.peer);self.download+=len(data)
            async def control():
                await reader.read(1)
            jobs=[asyncio.create_task(fn()) for fn in [send,receive,control]]
            done,_=await asyncio.wait(jobs,return_when=asyncio.FIRST_COMPLETED)
            for task in done:task.result()
        finally:
            for task in jobs:task.cancel()
            if jobs:await asyncio.gather(*jobs,return_exceptions=True)
            if transport:transport.close();protocol.clear()
            remote_writer.close()
    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task)
        remote_writer=None;counted=False;replied=False
        try:
            if self.closed or len(self.tasks)>128:return
            async def read(n):return await asyncio.wait_for(reader.readexactly(n),15)
            version,count=await read(2)
            if version!=5 or count<1:return
            if 0 not in await read(count):
                writer.write(b'\x05\xff');await writer.drain();return
            writer.write(b'\x05\x00');await writer.drain()
            version,command,reserved,atyp=await read(4)
            if version!=5 or reserved:return
            if command not in [1,3]:
                writer.write(b'\x05\x07\x00\x01'+b'\0'*6);await writer.drain();return
            if atyp==1:host=socket.inet_ntop(socket.AF_INET,await read(4))
            elif atyp==4:host=socket.inet_ntop(socket.AF_INET6,await read(16))
            elif atyp==3:
                length=(await read(1))[0]
                if not length:return
                host=(await read(length)).decode('ascii')
            else:return
            port=struct.unpack('!H',await read(2))[0]
            self.connections+=1;counted=True
            if command==3:
                # Keep the UDP association alive only while its TCP control stream lives.
                await self.udp(reader,writer,port);return
            remote_reader,remote_writer=await self.remote('connect',host,port)
            writer.transport.set_write_buffer_limits(high=self.hardware.chunk,low=self.hardware.chunk//4)
            writer.write(b'\x05\x00\x00\x01'+b'\0'*6);await writer.drain();replied=True
            def count(direction,length):
                if direction=='up':self.upload+=length
                else:self.download+=length
            await relay_streams(reader,writer,remote_reader,remote_writer,count,chunk_size=self.hardware.chunk if self.connections<=16 else 65536)
        except asyncio.CancelledError:raise
        except Exception:
            self.failures+=1
            if not replied:
                try:writer.write(b'\x05\x01\x00\x01'+b'\0'*6);await writer.drain()
                except Exception:pass
        finally:
            if counted:self.connections-=1
            if remote_writer:remote_writer.close()
            writer.close()
            try:await writer.wait_closed()
            except Exception:pass
            self.tasks.discard(task)
