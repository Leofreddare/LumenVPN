"""Windowed client control for the bundled native, pinned TLS transport."""
import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from windows_engine import file_hash
from hardware import detect

ROOT=Path(__file__).resolve().parent
class NativeTunnel:
    def __init__(self,profile,capabilities=(),executable=None,options=None):
        self.profile=profile;self.profile.validate();self.capabilities=capabilities
        self.options=options or {}
        self.executable=Path(executable) if executable else ROOT/'bin/lumen-transport.exe'
        self.verify=executable is None;self.process=None;self.reader_task=None
        self.upload=self.download=0;self.error=None
    async def start(self):
        if self.verify:
            manifest=json.loads((ROOT/'engine-manifest.json').read_text())
            if not self.executable.is_file() or file_hash(self.executable)!=manifest['transport_sha256']:
                raise RuntimeError('The bundled Lumen transport is missing or damaged. Extract the complete ZIP again.')
        self.process=await asyncio.create_subprocess_exec(str(self.executable),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,creationflags=0x08000000 if os.name=='nt' else 0)
        request=asdict(self.profile);request['fingerprint']=self.profile.validate();request['warm']='warm' in self.capabilities and self.options.get('warm_connections',True)
        request['chunk']={'64 KiB':65536,'128 KiB':131072,'256 KiB':262144}.get(self.options.get('stream_buffer'),detect().chunk)
        for key in ['dial_timeout', 'request_timeout', 'tcp_keepalive', 'warm_count', 'warm_lifetime', 'warm_retry', 'max_connections', 'idle_timeout', 'udp_queue_packets', 'udp_batch_packets', 'session_resumption', 'allow_udp']:
            if key in self.options:request[key]=self.options[key]
        try:
            self.process.stdin.write(json.dumps(request,separators=(',',':')).encode()+b'\n');await self.process.stdin.drain()
            line=await asyncio.wait_for(self.process.stdout.readline(),15)
            if len(line)>1024 or not json.loads(line).get('ready'):raise RuntimeError('The local transport could not start.')
        except BaseException:
            await self.stop();raise
        self.reader_task=asyncio.create_task(self.read_stats())
    async def read_stats(self):
        try:
            while line:=await self.process.stdout.readline():
                if len(line)>1024:raise ValueError()
                data=json.loads(line)
                if data.get('error'):raise ValueError()
                self.upload=int(data.get('up',self.upload));self.download=int(data.get('down',self.download))
            self.error='The local VPN transport stopped. Reconnect to try again.'
        except Exception:self.error='The local VPN transport stopped. Reconnect to try again.'
    async def stop(self):
        if self.process:
            if self.process.returncode is None:
                self.process.stdin.close()
                try:await asyncio.wait_for(self.process.wait(),5)
                except asyncio.TimeoutError:self.process.kill();await self.process.wait()
            if self.reader_task:
                self.reader_task.cancel();await asyncio.gather(self.reader_task,return_exceptions=True);self.reader_task=None
        self.upload=self.download=0
