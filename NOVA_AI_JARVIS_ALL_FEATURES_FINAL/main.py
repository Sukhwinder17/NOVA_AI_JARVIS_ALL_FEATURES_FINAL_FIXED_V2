from __future__ import annotations
import os, sys, time, threading
from pathlib import Path

# Windows: keep helper processes out of the console.
if os.name=='nt':
    import subprocess
    _orig_popen=subprocess.Popen
    class _Popen(_orig_popen):
        def __init__(self,*a,**kw):
            kw['creationflags']=kw.get('creationflags',0)|subprocess.CREATE_NO_WINDOW
            super().__init__(*a,**kw)
    subprocess.Popen=_Popen

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from core import config
config.sync_legacy_config()
from core.orchestrator import NovaOrchestrator
from core.phone_notification_server import PhoneNotificationServer
from ui import NovaWindow

APP_DIR=Path(__file__).resolve().parent

def main():
    app=QApplication(sys.argv)
    app.setApplicationName('NOVA AI')
    orchestrator=NovaOrchestrator()
    phone_notification_server = PhoneNotificationServer()
    phone_notification_server.start()
    win=NovaWindow(orchestrator)
    # Global Ctrl+Space push-to-talk on Windows where available.
    try:
        import keyboard
        def toggle():
            if win.listening: win.stop_listening()
            else: win.start_listening()
        keyboard.add_hotkey('ctrl+space',toggle)
    except Exception:
        pass
    return app.exec()

if __name__=='__main__':
    raise SystemExit(main())
