from __future__ import annotations

import base64
import ctypes
import hashlib
import hmac
import json
import os
import secrets
import threading
from ctypes import wintypes
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_FILE = _ROOT / "data" / "whatsapp" / "security.json"
_ITERATIONS = 600_000
_lock = threading.RLock()
_unlocked = False
_token = None


def _read():
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _write(data):
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(_FILE)
    try:
        os.chmod(_FILE, 0o600)
    except OSError:
        pass


def is_configured():
    return bool(_read().get("password_hash"))


def is_unlocked():
    return _unlocked


def setup_password(password: str):
    global _unlocked
    if os.name != "nt":
        raise RuntimeError("WhatsApp security requires Windows.")
    if is_configured():
        raise RuntimeError("A WhatsApp password is already configured.")
    if len(password) < 10:
        raise ValueError("Use at least 10 characters for the WhatsApp password.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    _write({"version": 1, "iterations": _ITERATIONS,
            "salt": base64.b64encode(salt).decode(),
            "password_hash": base64.b64encode(digest).decode()})
    _unlocked = True


def unlock(password: str) -> bool:
    global _unlocked
    data = _read()
    if not data.get("password_hash"):
        raise RuntimeError("No password set. Run /whatsapp setup first.")
    salt = base64.b64decode(data["salt"])
    expected = base64.b64decode(data["password_hash"])
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(data["iterations"]))
    _unlocked = hmac.compare_digest(actual, expected)
    return _unlocked


def lock():
    global _unlocked, _token
    with _lock:
        _unlocked = False
        _token = None


def require_unlocked():
    if not _unlocked:
        raise PermissionError("WhatsApp is locked. Use /whatsapp unlock in NOVA first.")


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(raw: bytes):
    buf = ctypes.create_string_buffer(raw)
    return _BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def _dpapi(raw: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is available only on Windows.")
    crypt = ctypes.windll.crypt32
    kernel = ctypes.windll.kernel32
    src, keep = _blob(raw)
    dst = _BLOB()
    if protect:
        ok = crypt.CryptProtectData(ctypes.byref(src), "NOVA WhatsApp token", None, None, None, 0, ctypes.byref(dst))
    else:
        ok = crypt.CryptUnprotectData(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        kernel.LocalFree(dst.pbData)


def save_token(token: str):
    require_unlocked()
    if not token.strip():
        raise ValueError("Token cannot be empty.")
    data = _read()
    data["token_dpapi"] = base64.b64encode(_dpapi(token.strip().encode("utf-8"), True)).decode("ascii")
    _write(data)


def get_token() -> str:
    require_unlocked()
    encoded = _read().get("token_dpapi")
    if not encoded:
        raise RuntimeError("No encrypted WPPConnect token saved. Run /whatsapp token after unlocking.")
    return _dpapi(base64.b64decode(encoded), False).decode("utf-8")
