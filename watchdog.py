"""Stop the native engine if its Python parent exits unexpectedly (Windows only)."""
import ctypes, sys
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.restype=ctypes.c_void_p
k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
k.TerminateProcess.argtypes=[ctypes.c_void_p,ctypes.c_uint]
k.CloseHandle.argtypes=[ctypes.c_void_p]
parent=k.OpenProcess(0x100000,False,int(sys.argv[1]));child=k.OpenProcess(0x100001,False,int(sys.argv[2]))
if parent and child:
    while k.WaitForSingleObject(parent,1000)==258:
        if k.WaitForSingleObject(child,0)==0:break
    else:
        if k.WaitForSingleObject(child,0)==258:k.TerminateProcess(child,1)
for handle in (parent,child):
    if handle:k.CloseHandle(handle)
