from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
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
    "messages": "com.google.android.apps.messaging",
    "messaging": "com.google.android.apps.messaging",
    "sms": "com.google.android.apps.messaging",
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
        if line and not line.startswith("*") and "	device" in line:
            serial = line.split("	", 1)[0]
            if "._adb-tls-connect._tcp" not in serial:
                rows.append(serial)
    rows.sort(key=lambda s: (0 if ":" in s and s.rsplit(":", 1)[-1].isdigit() else 1, s))
    return rows

def _mdns_addresses() -> list[str]:
    """Discover wireless-debugging endpoints advertised by Android's mDNS service."""
    try:
        out = _run("mdns", "services", timeout=5)
    except Exception:
        return []
    found = []
    for line in out.splitlines():
        if "_adb-tls-connect._tcp" not in line:
            continue
        match = re.search(r"(\d{1,3}(?:\.\d{1,3}){3}:\d+)", line)
        if match and match.group(1) not in found:
            found.append(match.group(1))
    return found

def _restore_connection(address: str) -> str:
    """Reconnect to a known ADB endpoint and recreate NOVA's reverse tunnel."""
    _run("connect", address, timeout=10)
    ds = devices()
    if not ds:
        return ""
    serial = next((d for d in ds if d == address), ds[0])
    os.environ["NOVA_PHONE_ADDRESS"] = serial
    try:
        _run("-s", serial, "reverse", "tcp:8765", "tcp:8765")
    except Exception:
        pass
    return serial

def _serial() -> str:
    ds = devices()
    if ds:
        return ds[0]

    saved = os.getenv("NOVA_PHONE_ADDRESS", "").strip()
    if saved:
        try:
            serial = _restore_connection(saved)
            if serial:
                return serial
        except Exception:
            pass

    # Wireless debugging can remain discoverable through mDNS even after the
    # active ADB transport drops. Recover automatically from the advertised endpoint.
    for address in _mdns_addresses():
        try:
            serial = _restore_connection(address)
            if serial:
                return serial
        except Exception:
            continue
    return ""

def connect(address: str = "") -> str:
    address = address.strip()
    if address:
        out = _run("connect", address, timeout=10)
        serial = _restore_connection(address)
        if not serial:
            return f"ADB did not establish a usable connection to {address}. {out}".strip()
        return f"Phone connected: {serial}"

    serial = _serial()
    if not serial:
        return "No Android phone detected. Wireless debugging may be off or the phone may be unavailable."
    try:
        _run("-s", serial, "reverse", "tcp:8765", "tcp:8765")
    except Exception:
        pass
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

def schedule_sms(recipient: str, message: str, trigger_at_ms: int) -> str:
    """Store a one-time SMS schedule on the phone.
    Uses a relative delay when communicating with the phone so clock skew
    between the laptop and phone cannot reject a valid future schedule.
    """
    serial = _serial()
    if not serial:
        return "No Android phone connected."

    raw_recipient = str(recipient or "").strip()
    message = str(message or "").strip()
    if not raw_recipient:
        return "Please specify the SMS recipient phone number."
    if not message:
        return "Please specify the SMS message."

    cleaned = re.sub(r"[^0-9+]", "", raw_recipient)
    if cleaned.startswith("++") or ("+" in cleaned[1:]):
        return "Please provide a valid SMS phone number."
    if len(re.sub(r"\D", "", cleaned)) < 5:
        return "Please provide a valid SMS phone number."

    try:
        trigger = int(trigger_at_ms)
    except Exception:
        return "Invalid scheduled time."

    now_ms = int(time.time() * 1000)
    delay_ms = trigger - now_ms
    if delay_ms <= 1000:
        return "The scheduled time must be in the future."

    request_id = uuid.uuid4().hex
    try:
        out = _run(
            "-s", serial, "shell", "am", "broadcast",
            "-n", "com.nova.phone/.NovaScheduledSmsReceiver",
            "-a", "com.nova.phone.SCHEDULE_SMS",
            "--es", "request_id", request_id,
            "--es", "recipient", cleaned,
            "--es", "message", message,
            "--el", "delay_ms", str(delay_ms),
            timeout=20,
        )
    except Exception as exc:
        return f"Could not schedule SMS: {exc}"

    lower = (out or "").lower()
    if "result=3" in lower:
        return "Scheduled SMS needs the phone's Alarms & reminders access. Open NOVA Phone Companion and allow it."
    if "result=5" in lower:
        return f"SMS scheduling failed on the phone: {out}"
    if "result=2" in lower:
        return f"SMS schedule was rejected: {out}"
    if "result=-1" not in lower and "result=0" not in lower:
        return f"SMS schedule did not start correctly: {out or 'unknown ADB result'}"

    from datetime import datetime
    when = datetime.fromtimestamp(trigger / 1000).astimezone().strftime("%Y-%m-%d %I:%M %p")
    return f"⏰ SMS scheduled on your phone for {when} to {raw_recipient}. The laptop does not need to stay connected; the phone will open the SMS composer at that time."

def send_sms(recipient: str, message: str) -> str:
    """Send a real SMS in the background and wait for the Android telephony result."""
    serial = _serial()
    if not serial:
        return "No Android phone connected."

    raw_recipient = str(recipient or "").strip()
    message = str(message or "").strip()
    if not raw_recipient:
        return "Please specify the SMS recipient phone number."
    if not message:
        return "Please specify the SMS message."

    cleaned = re.sub(r"[^0-9+]", "", raw_recipient)
    if cleaned.startswith("++") or ("+" in cleaned[1:]):
        return "Please provide a valid SMS phone number."
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 5:
        return "Please provide a valid SMS phone number."

    request_id = uuid.uuid4().hex
    try:
        out = _run(
            "-s", serial, "shell", "am", "broadcast",
            "-n", "com.nova.phone/.NovaSmsReceiver",
            "-a", "com.nova.phone.SEND_SMS",
            "--es", "request_id", request_id,
            "--es", "recipient", cleaned,
            "--es", "message", message,
            timeout=20,
        )
    except Exception as exc:
        return f"SMS send failed: {exc}"

    lower = (out or "").lower()
    if "result=3" in lower:
        return "SMS permission is not granted to NOVA Phone Companion. Open the companion once and allow SMS permission."
    if "result=4" in lower:
        return "This phone does not support SMS sending through Android's SMS API."
    if "result=5" in lower:
        return f"SMS send failed on the phone: {out}"
    if "result=2" in lower:
        return f"SMS request was rejected: {out}"
    # Android's Activity.RESULT_OK is -1. Older companion code used 0.
    # Accept either value because both mean the BroadcastReceiver accepted
    # the SMS send request. The real telephony result is checked below.
    if "result=-1" not in lower and "result=0" not in lower:
        return f"SMS request did not start correctly: {out or 'unknown ADB result'}"

    # result=0 only means the Android receiver accepted the request. Wait for
    # the asynchronous SmsManager PendingIntent result before claiming success.
    try:
        from .phone_notification_server import read_sms_status
        deadline = time.time() + 20
        while time.time() < deadline:
            statuses = read_sms_status(request_id)
            if statuses:
                failed = next((s for s in statuses if s.get("status") == "failed"), None)
                if failed:
                    reason = failed.get("result") or failed.get("result_code") or "unknown failure"
                    return f"❌ SMS was not sent to {raw_recipient}: {reason}."

                total = max(int(s.get("total", 1) or 1) for s in statuses)
                sent_parts = {
                    int(s.get("part", 0) or 0)
                    for s in statuses
                    if s.get("status") in ("sent", "delivered")
                }
                if len(sent_parts) >= total:
                    return f"📨 SMS sent successfully to {raw_recipient}."
            time.sleep(0.25)
    except Exception:
        pass

    return (
        f"⚠️ Android accepted the SMS request for {raw_recipient}, "
        "but no telephony send confirmation arrived. Check the phone's signal/SIM/default SMS subscription."
    )

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
    if action in ("schedule_sms", "sms_schedule"): return schedule_sms(
        str(kwargs.get("recipient", kwargs.get("number", ""))),
        str(kwargs.get("message", "")),
        int(kwargs.get("trigger_at_ms", 0)),
    )
    if action in ("send_sms", "sms", "text_message"): return send_sms(
        str(kwargs.get("recipient", kwargs.get("number", ""))),
        str(kwargs.get("message", "")),
    )
    if action == "open_url": return open_url(str(kwargs.get("url", "")))
    if action in ("launch_app", "open_app"): return launch_app(str(kwargs.get("app", "")))
    if action == "screenshot": return screenshot()
    if action in ("clipboard_get", "read_clipboard"): return clipboard_get()
    if action in ("clipboard_set", "copy_to_phone"): return clipboard_set(str(kwargs.get("text", "")))
    if action == "volume": return volume(str(kwargs.get("direction", "")))
    if action == "media": return media(str(kwargs.get("media_action", "")))
    if action == "disconnect": return disconnect()
    if action == "devices": return connect("")
    return "Phone actions: connect, status, info, battery, notify, send_sms, open_url, launch_app, screenshot, clipboard_get, clipboard_set, volume, media, disconnect."
