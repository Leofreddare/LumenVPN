"""Signal the hidden engine console so windowed Python can stop it gracefully."""
import ctypes,sys
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.AttachConsole.argtypes=[ctypes.c_ulong];k.AttachConsole.restype=ctypes.c_int
k.GenerateConsoleCtrlEvent.argtypes=[ctypes.c_ulong,ctypes.c_ulong];k.GenerateConsoleCtrlEvent.restype=ctypes.c_int
HANDLER=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_ulong)
@HANDLER
def ignore(event):return 1
k.SetConsoleCtrlHandler.argtypes=[HANDLER,ctypes.c_int]
if not k.AttachConsole(int(sys.argv[1])):raise SystemExit(1)
k.SetConsoleCtrlHandler(ignore,True)
ok=k.GenerateConsoleCtrlEvent(1,0)
k.FreeConsole()
raise SystemExit(0 if ok else 1)
