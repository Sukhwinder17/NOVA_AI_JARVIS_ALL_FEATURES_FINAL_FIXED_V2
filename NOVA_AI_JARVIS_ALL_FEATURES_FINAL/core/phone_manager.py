from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

def _adb() -> str:
    return shutil.which("adb") or os.getenv("NOVA_ADB", "adb")

def _run(*args: str, timeout: int = 15) -> str:
    cmd = [_adb(), *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except FileNotFoundError:
        raise RuntimeError("ADB is not installed or not on PATH. Install Android Platform Tools and enable USB/Wireless debugging.")
    except Exception as exc:
        raise RuntimeError(f"Could not run ADB: {exc}")
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0:
        raise RuntimeError(err or out or f"ADB exited with code {p.returncode}")
    return out

def devices() -> list[str]:
    out = _run("devices")
    rows=[]
    for line in out.splitlines()[1:]:
        line=line.strip()
        if line and not line.startswith("*") and "\tdevice" in line:
            rows.append(line.split("\t",1)[0])
    return rows

def connect(address: str = "") -> str:
    address = address.strip()
    if address:
        out = _run("connect", address)
        return out or f"Connected to {address}."
    ds=devices()
    if not ds:
        return "No Android phone detected. Connect it by USB, or run 'adb pair IP:PORT' and then 'adb connect IP:PORT'."
    return f"Phone connected: {ds[0]}"

def status() -> str:
    ds=devices()
    if not ds:
        return "No Android phone connected."
    serial=ds[0]
    model=_run("-s",serial,"shell","getprop","ro.product.model")
    battery=_run("-s",serial,"shell","dumpsys","battery")
    level="unknown"
    for line in battery.splitlines():
        if "level:" in line:
            level=line.split(":",1)[1].strip()
            break
    return f"📱 {model or 'Android phone'} — battery {level}% — connected."

def notify(title: str, message: str) -> str:
    ds=devices()
    if not ds: return "No Android phone connected."
    serial=ds[0]
    _run("-s",serial,"shell","cmd","notification","post","-S","bigtext","nova_ai",title,message)
    return "Notification sent to your phone."

def open_url(url: str) -> str:
    ds=devices()
    if not ds: return "No Android phone connected."
    _run("-s",ds[0],"shell","am","start","-a","android.intent.action.VIEW","-d",url)
    return f"Opened {url} on your phone."

def screenshot() -> str:
    ds=devices()
    if not ds: return "No Android phone connected."
    out_dir=BASE/"data"/"phone"
    out_dir.mkdir(parents=True,exist_ok=True)
    path=out_dir/"phone_screenshot.png"
    try:
        raw=subprocess.run([_adb(),"-s",ds[0],"exec-out","screencap","-p"],capture_output=True,timeout=20)
        if raw.returncode!=0: raise RuntimeError((raw.stderr or b"").decode(errors="replace"))
        path.write_bytes(raw.stdout)
    except Exception as exc:
        raise RuntimeError(f"Phone screenshot failed: {exc}")
    return str(path)

def disconnect() -> str:
    ds=devices()
    if not ds: return "No Android phone is currently connected."
    for serial in ds:
        try: _run("disconnect",serial)
        except Exception: pass
    return "Phone disconnected."

def phone_command(action: str, **kwargs) -> str:
    action=action.lower().strip()
    if action=="connect": return connect(str(kwargs.get("address","")))
    if action in ("status","battery"): return status()
    if action=="notify": return notify(str(kwargs.get("title","NOVA AI")),str(kwargs.get("message","")))
    if action=="open_url": return open_url(str(kwargs.get("url","")))
    if action=="screenshot": return screenshot()
    if action=="disconnect": return disconnect()
    if action=="devices": return connect("")
    return "Phone actions: connect, status, battery, notify, open_url, screenshot, disconnect."
