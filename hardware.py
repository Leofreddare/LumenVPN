"""Local-only resource detection and bounded streaming policy."""
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Hardware:
    cpus: int
    memory: int
    chunk: int

def policy(cpus,memory):
    cpus=max(1,int(cpus));memory=max(0,int(memory))
    chunk=262144 if cpus>=2 and memory>=1073741824 else 131072 if memory>=536870912 else 65536
    return Hardware(cpus,memory,chunk)

def detect():
    try:cpus=len(os.sched_getaffinity(0))
    except (AttributeError,OSError):cpus=os.cpu_count() or 1
    memory=0
    if os.name=='nt':
        try:
            import ctypes
            class Status(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
            status=Status();status.length=ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):memory=status.available
        except (AttributeError,OSError):pass
    else:
        try:memory=os.sysconf('SC_AVPHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
        except (ValueError,OSError,AttributeError):pass
        # Respect common cgroup memory/CPU limits rather than the host's size.
        for folder,memfile,usedfile in [('/sys/fs/cgroup','memory.max','memory.current'),('/sys/fs/cgroup/memory','memory.limit_in_bytes','memory.usage_in_bytes')]:
            try:
                limit=int((Path(folder)/memfile).read_text());used=int((Path(folder)/usedfile).read_text())
                remaining=max(0,limit-used);memory=min(memory,remaining) if memory else remaining
            except (OSError,ValueError):pass
        try:
            quota,period=(Path('/sys/fs/cgroup/cpu.max').read_text().split())
            cpus=min(cpus,max(1,(int(quota)+int(period)-1)//int(period)))
        except (OSError,ValueError):pass
    return policy(cpus,memory)
