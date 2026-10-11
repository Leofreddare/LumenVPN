"""Windows virtual adapter. Transport remains the user's Lumen relay."""
import ctypes, hashlib, ipaddress, json, os, secrets, signal, socket, subprocess, tempfile, time, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def configuration(endpoint, socks_port, api_port, secret, options=None):
    ip=ipaddress.ip_address(endpoint)
    options=options or {}
    return {'log':{'disabled':True}, 'dns':{'servers':[{'type':'tls','tag':'secure-dns','server':options.get('dns_server','1.1.1.1'),'server_port':options.get('dns_port',853),'tls':{'enabled':True,'server_name':options.get('dns_name','cloudflare-dns.com')},'detour':'relay'}],'final':'secure-dns'},
      'inbounds':[{'type':'tun','tag':'system','interface_name':'Lumen','address':['172.28.0.1/30','fdfe:dcba:9876::1/126'],'mtu':options.get('mtu',1400),'auto_route':True,'strict_route':True,'route_exclude_address':[f'{ip}/{ip.max_prefixlen}'],'stack':{'Mixed':'mixed','System':'system','gVisor':'gvisor'}.get(options.get('tun_stack','Mixed'),'mixed')}],
      'outbounds':[{'type':'socks','tag':'relay','server':'127.0.0.1','server_port':socks_port,'version':'5'}],
      'route':{'rules':([{'ip_version':6,'action':'reject'}] if options.get('block_ipv6') else [])+[{'port':53,'action':'hijack-dns'},{'network':'icmp','action':'reject'}],'final':'relay'},
      'experimental':{'clash_api':{'external_controller':f'127.0.0.1:{api_port}','secret':secret}}}


def file_hash(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):digest.update(chunk)
    return digest.hexdigest()

def ensure_components():
    manifest=json.loads((ROOT/'engine-manifest.json').read_text())
    def valid():
        return all((ROOT/'bin'/name).is_file() and file_hash(ROOT/'bin'/name)==manifest[key]
                   for name,key in [('sing-box.exe','engine_sha256'),('wintun.dll','wintun_sha256')])
    if not valid():raise RuntimeError('A bundled networking component is missing or damaged. Extract the complete Lumen ZIP again. No files have been downloaded.')

class WindowsEngine:
    def __init__(self,options=None): self.options=options or {};self.process=None;self.directory=None;self.secret=secrets.token_hex(32);self.job=None
    def start(self, endpoint, port):
        if os.name!='nt':raise RuntimeError('Full-system routing requires Windows.')
        if not ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('Run app.py and accept the Windows administrator prompt.')
        ensure_components()
        with socket.socket() as s:s.bind(('127.0.0.1',0));api_port=s.getsockname()[1]
        self.directory=tempfile.TemporaryDirectory(prefix='lumen-')
        config=Path(self.directory.name)/'config.json';config.write_text(json.dumps(configuration(endpoint,port,api_port,self.secret,self.options)))
        startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
        self.process=subprocess.Popen([str(ROOT/'bin'/'sing-box.exe'),'run','-c',str(config)],cwd=ROOT/'bin',stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        # Parent-death watchdog stops the adapter if the GUI crashes.
        self.watchdog=subprocess.Popen([os.sys.executable,str(ROOT/'watchdog.py'),str(os.getpid()),str(self.process.pid)],creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            if self.process.poll() is not None:
                details=self.process.stderr.read(4096).decode(errors='replace')
                self.stop();raise RuntimeError('Windows adapter could not start. '+details[-1000:])
            try:
                req=urllib.request.Request(f'http://127.0.0.1:{api_port}/version',headers={'Authorization':'Bearer '+self.secret})
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open(req,timeout=.5) as r:
                    if r.status==200:
                        # API readiness alone does not prove the adapter is present.
                        result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',"if (Get-NetAdapter -Name Lumen -ErrorAction SilentlyContinue | Where-Object Status -eq Up) {exit 0} else {exit 1}"],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=5)
                        if result.returncode==0:return
            except (OSError,subprocess.TimeoutExpired):pass
            time.sleep(.2)
        self.stop();raise RuntimeError('Windows adapter did not become ready within 20 seconds.')
    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                subprocess.run([os.sys.executable,str(ROOT/'console_break.py'),str(self.process.pid)],creationflags=subprocess.CREATE_NO_WINDOW,timeout=3,check=True)
                self.process.wait(timeout=8)
            except (OSError,subprocess.TimeoutExpired,subprocess.CalledProcessError):self.process.kill();self.process.wait()
        if self.process and self.process.stderr:self.process.stderr.close()
        if self.directory:self.directory.cleanup();self.directory=None
