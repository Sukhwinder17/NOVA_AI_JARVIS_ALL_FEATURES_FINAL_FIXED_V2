from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

APP_PACKAGES = {
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "google chrome": "com.android.chrome",
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "facebook": "com.facebook.katana",
    "spotify": "com.spotify.music",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "settings": "com.android.settings",
    "play store": "com.android.vending",
    "google play": "com.android.vending",
    "phone": "com.android.dialer",
    "contacts": "com.android.contacts",
    "camera": "com.android.camera",
}

def _adb() -> str:
    return shutil.which("adb") or os.getenv("NOVA_ADB", "adb")

def _run(*args: str, timeout: int = 15) -> str:
    cmd = [_adb(), *args]
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ADB is not installed or not on PATH. Install Android Platform Tools and enable USB/Wireless debugging."
        )
    except Exception as exc:
        raise RuntimeError(f"Could not run ADB: {exc}")
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if p.returncode != 0:
        raise RuntimeError(err or out or f"ADB exited with code {p.returncode}")
    return out

def devices() -> list[str]:
    out = _run("devices")
    rows = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if line and not line.startswith("*") and "\tdevice" in line:
            serial = line.split("\t", 1)[0]
            if "._adb-tls-connect._tcp" not in serial:
                rows.append(serial)
    rows.sort(key=lambda s: (0 if ":" in s and s.rsplit(":", 1)[-1].isdigit() else 1, s))
    return rows

def _serial() -> str:
    ds = devices()
    if ds:
        return ds[0]
    saved = os.getenv("NOVA_PHONE_ADDRESS", "").strip()
    if saved:
        try:
            _run("connect", saved)
            ds = devices()
            if ds:
                return ds[0]
        except Exception:
            pass
    return ""

def connect(address: str = "") -> str:
    address = address.strip()
    if address:
        out = _run("connect", address)
        os.environ["NOVA_PHONE_ADDRESS"] = address
        return out or f"Connected to {address}."
    serial = _serial()
    if not serial:
        return "No Android phone detected. Connect it by USB, or run 'adb pair IP:PORT' and then 'adb connect IP:PORT'."
    return f"Phone connected: {serial}"

def status() -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    model = _run("-s", serial, "shell", "getprop", "ro.product.model")
    battery = _run("-s", serial, "shell", "dumpsys", "battery")
    level = "unknown"
    charging = "unknown"
    for line in battery.splitlines():
        if "level:" in line:
            level = line.split(":", 1)[1].strip()
        if "status:" in line:
            raw = line.split(":", 1)[1].strip()
            charging = {"2": "charging", "3": "discharging", "4": "not charging", "5": "full"}.get(raw, raw)
    return f"📱 {model or 'Android phone'} — battery {level}% — {charging} — connected."

def info() -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    model = _run("-s", serial, "shell", "getprop", "ro.product.model")
    brand = _run("-s", serial, "shell", "getprop", "ro.product.brand")
    android = _run("-s", serial, "shell", "getprop", "ro.build.version.release")
    sdk = _run("-s", serial, "shell", "getprop", "ro.build.version.sdk")
    return f"📱 {brand} {model} — Android {android} (API {sdk}) — ADB {serial}"

def notify(title: str, message: str) -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    _run("-s", serial, "shell", "cmd", "notification", "post", "-S", "bigtext", "nova_ai", title, message)
    return "🔔 Notification sent to your phone."

def open_url(url: str) -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    _run("-s", serial, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url)
    return f"🌐 Opened {url} on your phone."

def launch_app(app: str) -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    name = app.strip().lower()
    package = APP_PACKAGES.get(name, app.strip())
    if not package:
        return "Tell me which phone app to open."
    _run("-s", serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
    return f"📱 Opened {app.strip()} on your phone."

def screenshot() -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    out_dir = BASE / "data" / "phone"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "phone_screenshot.png"
    try:
        raw = subprocess.run(
            [_adb(), "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=20,
        )
        if raw.returncode != 0:
            raise RuntimeError((raw.stderr or b"").decode(errors="replace"))
        path.write_bytes(raw.stdout)
    except Exception as exc:
        raise RuntimeError(f"Phone screenshot failed: {exc}")
    return str(path)

def clipboard_get() -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    try:
        value = _run("-s", serial, "shell", "cmd", "clipboard", "get")
    except RuntimeError:
        value = _run("-s", serial, "shell", "service", "call", "clipboard", "1")
    return f"📋 Phone clipboard: {value or '(empty)'}"

def clipboard_set(text: str) -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    if not text:
        return "Tell me what to copy to your phone."
    _run("-s", serial, "shell", "cmd", "clipboard", "set", text)
    return "📋 Copied to your phone clipboard."

def volume(direction: str) -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    d = direction.lower().strip()
    key = {
        "up": "KEYCODE_VOLUME_UP",
        "down": "KEYCODE_VOLUME_DOWN",
        "mute": "KEYCODE_VOLUME_MUTE",
    }.get(d)
    if not key:
        return "Volume actions: up, down, mute."
    _run("-s", serial, "shell", "input", "keyevent", key)
    return f"🔊 Phone volume {d}."

def media(action: str) -> str:
    serial = _serial()
    if not serial:
        return "No Android phone connected."
    key = {
        "play": "KEYCODE_MEDIA_PLAY",
        "pause": "KEYCODE_MEDIA_PAUSE",
        "play_pause": "KEYCODE_MEDIA_PLAY_PAUSE",
        "next": "KEYCODE_MEDIA_NEXT",
        "previous": "KEYCODE_MEDIA_PREVIOUS",
        "prev": "KEYCODE_MEDIA_PREVIOUS",
    }.get(action.lower().strip())
    if not key:
        return "Media actions: play, pause, next, previous."
    _run("-s", serial, "shell", "input", "keyevent", key)
    return f"🎵 Media command: {action}."

def disconnect() -> str:
    ds = devices()
    if not ds:
        return "No Android phone is currently connected."
    for serial in ds:
        try:
            _run("disconnect", serial)
        except Exception:
            pass
    return "Phone disconnected."

def phone_command(action: str, **kwargs) -> str:
    action = action.lower().strip()
    if action == "connect": return connect(str(kwargs.get("address", "")))
    if action in ("status", "battery"): return status()
    if action == "info": return info()
    if action == "notify": return notify(str(kwargs.get("title", "NOVA AI")), str(kwargs.get("message", "")))
    if action == "open_url": return open_url(str(kwargs.get("url", "")))
    if action in ("launch_app", "open_app"): return launch_app(str(kwargs.get("app", "")))
    if action == "screenshot": return screenshot()
    if action in ("clipboard_get", "read_clipboard"): return clipboard_get()
    if action in ("clipboard_set", "copy_to_phone"): return clipboard_set(str(kwargs.get("text", "")))
    if action == "volume": return volume(str(kwargs.get("direction", "")))
    if action == "media": return media(str(kwargs.get("media_action", "")))
    if action == "disconnect": return disconnect()
    if action == "devices": return connect("")
    return "Phone actions: connect, status, info, battery, notify, open_url, launch_app, screenshot, clipboard_get, clipboard_set, volume, media, disconnect."
