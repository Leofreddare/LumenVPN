"""Local Unbound DNSSEC validator; upstream DNS-over-TLS stays inside the VPN."""
import hashlib,ipaddress,json,os,re,socket,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def dns_configuration(port,directory,options=None):
    options=options or {};address=str(ipaddress.ip_address(options.get('dns_server','1.1.1.1')))
    hostname=options.get('dns_name','cloudflare-dns.com');upstream_port=options.get('dns_port',853)
    if not isinstance(hostname,str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,253}',hostname):raise ValueError('Invalid DNS certificate hostname.')
    if type(upstream_port) is not int or not 1<=upstream_port<=65535:raise ValueError('Invalid DNS TLS port.')
    if type(port) is not int or not 1024<=port<=65535:raise ValueError('Invalid local DNS port.')
    def quote(path):return '"'+str(Path(path).resolve()).replace('\\','/').replace('"','\\"')+'"'
    return f'''server:
    interface: 127.0.0.1
    port: {port}
    access-control: 127.0.0.0/8 allow
    username: ""
    chroot: ""
    directory: {quote(directory)}
    do-daemonize: no
    pidfile: ""
    use-syslog: no
    logfile: ""
    verbosity: 0
    log-queries: no
    log-replies: no
    hide-identity: yes
    hide-version: yes
    num-threads: 1
    msg-cache-size: 4m
    rrset-cache-size: 8m
    key-cache-size: 2m
    neg-cache-size: 1m
    cache-min-ttl: 0
    cache-max-ttl: 3600
    cache-max-negative-ttl: 60
    serve-expired: no
    prefetch: no
    outgoing-range: 64
    outgoing-num-tcp: 16
    incoming-num-tcp: 16
    num-queries-per-thread: 64
    so-rcvbuf: 0
    so-sndbuf: 0
    do-ip6: {'yes' if ipaddress.ip_address(address).version==6 else 'no'}
    do-not-query-localhost: yes
    module-config: "validator iterator"
    trust-anchor-file: {quote(ROOT/'assets/root-trust-anchor.key')}
    tls-cert-bundle: {quote(ROOT/'assets/dns-ca.pem')}
    harden-dnssec-stripped: yes
    val-permissive-mode: no
    val-log-level: 0
    minimal-responses: yes
    edns-buffer-size: 1232
    tcp-upstream: yes
forward-zone:
    name: "."
    forward-tls-upstream: yes
    forward-first: no
    forward-addr: {address}@{upstream_port}#{hostname}
'''

class LocalDNS:
    def __init__(self,options=None):
        self.options=options or {};self.process=None;self.watchdog=None
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
    def start(self,directory):
        from windows_engine import file_hash
        manifest=json.loads((ROOT/'engine-manifest.json').read_text())
        for name,key in [('bin/unbound/unbound.exe','dns_sha256'),('assets/dns-ca.pem','dns_ca_sha256'),('assets/root-trust-anchor.key','dns_anchor_sha256')]:
            if file_hash(ROOT/name)!=manifest[key]:raise RuntimeError('A bundled DNS security component is damaged.')
        config=Path(directory)/'unbound.conf';config.write_text(dns_configuration(self.port,directory,self.options),encoding='utf-8')
        self.process=subprocess.Popen([str(ROOT/'bin/unbound/unbound.exe'),'-d','-c',str(config)],cwd=directory,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000 if os.name=='nt' else 0)
        self.watchdog=subprocess.Popen([os.sys.executable,str(ROOT/'watchdog.py'),str(os.getpid()),str(self.process.pid)],creationflags=0x08000000 if os.name=='nt' else 0)
        # Check the loopback listener only. Never send pre-tunnel probe queries.
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if self.process.poll() is not None:raise RuntimeError('The local DNS validator could not start.')
            try:
                with socket.create_connection(('127.0.0.1',self.port),timeout=.15):return
            except OSError:time.sleep(.025)
        raise RuntimeError('The local DNS validator did not become ready.')
    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
