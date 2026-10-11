"""Windowed Lumen VPN entry point. Uses the user's installed Python."""
try:
    from app import main
except ImportError as error:
    import os
    if os.name=='nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'A required Python package is missing. Install client/requirements.txt using your existing Python.\n\n'+str(error),'Lumen VPN',0x10)
    else:raise
else:
    main()
