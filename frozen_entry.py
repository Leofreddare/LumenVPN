"""Frozen entry point, including the existing Windows cleanup helpers."""
import sys
from pathlib import Path

if len(sys.argv)==3 and sys.argv[1]=='--export-notices':
    import shutil
    destination=Path(sys.argv[2])
    if destination.exists():raise SystemExit('Choose a new folder for the notices.')
    shutil.copytree(Path(__file__).resolve().parent/'third-party',destination)
    raise SystemExit(0)

if len(sys.argv)>1 and sys.argv[1]=='--lumen-helper':
    import runpy
    allowed={'watchdog','console_break'}
    if len(sys.argv)<3 or sys.argv[2] not in allowed:
        raise SystemExit(2)
    name=sys.argv[2]
    script=Path(__file__).resolve().parent/(name+'.py')
    sys.argv=[str(script),*sys.argv[3:]]
    runpy.run_path(str(script),run_name='__main__')
    raise SystemExit(0)

import widgets
from PySide6.QtGui import QIcon
def _packaged_icon():
    return QIcon(str(Path(__file__).resolve().parent/'assets/lumen.ico'))
widgets.logo_icon=_packaged_icon

from app import main
main()
