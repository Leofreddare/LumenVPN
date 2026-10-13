"""Bounded authenticated probes to user-saved servers only, without traffic logs."""
import time,socket
from PySide6.QtCore import QThread,Signal

async def measure(profile,timeout=4):
    import asyncio
    async def run():
        from core import choose_endpoint
        records=await asyncio.get_running_loop().getaddrinfo(profile.host,profile.port,type=socket.SOCK_STREAM)
        start=time.perf_counter();await choose_endpoint(profile,[item[4][0] for item in records])
        return (time.perf_counter()-start)*1000
    return await asyncio.wait_for(run(),timeout)

def level(latency,good=80,medium=180):
    if latency is None:return 0
    return 3 if latency<=good else 2 if latency<=medium else 1

class LatencyScanner(QThread):
    measured=Signal(str,object)
    def __init__(self,items,timeout=4,parent=None,concurrency=2):super().__init__(parent);self.items=items;self.concurrency=concurrency;self.timeout=timeout;self.loop=None;self.task=None;self.stopping=False
    def run(self):
        import asyncio
        self.loop=asyncio.new_event_loop();self.task=self.loop.create_task(self.scan())
        if self.stopping:self.task.cancel()
        try:self.loop.run_until_complete(self.task)
        except asyncio.CancelledError:pass
        finally:self.loop.close();self.loop=None
    async def scan(self):
        import asyncio
        semaphore=asyncio.Semaphore(self.concurrency)
        async def check(ident,profile):
            async with semaphore:
                if self.stopping:return
                try:value=await measure(profile,self.timeout)
                except Exception:value=None
                if not self.stopping:self.measured.emit(ident,value)
        # Only two open probes at a time; batches also bound task allocations.
        for offset in range(0,len(self.items),32):
            if self.stopping:return
            await asyncio.gather(*(check(*item) for item in self.items[offset:offset+32]))
    def stop(self):
        self.stopping=True
        if self.loop and self.task:
            try:self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:pass
