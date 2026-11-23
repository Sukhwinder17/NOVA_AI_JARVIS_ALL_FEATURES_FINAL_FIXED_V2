from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_BRIDGE_HOST = "127.0.0.1"
_BRIDGE_PORT = 8766
_PENDING = queue.Queue()
_WAITING: dict[str, tuple[threading.Event, dict]] = {}
_WAITING_LOCK = threading.Lock()
_SERVER = None


class _BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def _json(self, status: int, payload: dict):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if status != 204:
            self.wfile.write(raw)

    def do_OPTIONS(self):
        self._json(204, {})

    def do_GET(self):
        if self.path != "/next":
            self._json(404, {"error": "not found"})
            return
        try:
            command = _PENDING.get_nowait()
        except queue.Empty:
            self._json(200, {})
            return
        self._json(200, command)

    def do_POST(self):
        if self.path != "/complete":
            self._json(404, {"error": "not found"})
            return
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 20000)
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            request_id = str(data.get("id", ""))
            with _WAITING_LOCK:
                waiting = _WAITING.get(request_id)
            if waiting:
                event, result_box = waiting
                result_box["result"] = str(data.get("result", "WhatsApp task finished."))
                event.set()
            self._json(200, {"ok": True})
        except Exception as exc:
            self._json(400, {"error": str(exc)})


def _ensure_bridge():
    global _SERVER
    if _SERVER is not None:
        return True
    try:
        server = ThreadingHTTPServer((_BRIDGE_HOST, _BRIDGE_PORT), _BridgeHandler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, name="NOVA-WhatsApp-Bridge", daemon=True)
        thread.start()
        _SERVER = server
        return True
    except OSError:
        # A bridge already bound to the configured loopback port may be active.
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://{_BRIDGE_HOST}:{_BRIDGE_PORT}/next", timeout=1):
                return True
        except Exception:
            return False


def _whatsapp_web(receiver: str, message: str) -> str:
    if not _ensure_bridge():
        return "NOVA's local WhatsApp bridge could not start on 127.0.0.1:8766. Check whether another app is using that port. No message was sent."

    request_id = uuid.uuid4().hex
    event = threading.Event()
    result_box: dict = {}
    command = {"id": request_id, "receiver": receiver, "message": message}

    with _WAITING_LOCK:
        _WAITING[request_id] = (event, result_box)
    _PENDING.put(command)
    try:
        if not event.wait(timeout=210):
            return (
                "NOVA did not receive a response from its Chrome extension. "
                "Install/enable the NOVA WhatsApp Bridge extension, keep NOVA running, "
                "and reload the WhatsApp Web tab. No message was confirmed as sent."
            )
        return result_box.get("result", "WhatsApp bridge returned no result.")
    finally:
        with _WAITING_LOCK:
            _WAITING.pop(request_id, None)


def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    try:
        import pyautogui
        import pyperclip
        pyautogui.press("win")
        pyperclip.copy(app_name)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        pyautogui.sleep(2.5)
        pyautogui.hotkey("ctrl", "f")
        pyperclip.copy(receiver)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        pyautogui.sleep(0.8)
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        return f"Message send action completed for {receiver} via {app_name}."
    except Exception as exc:
        return f"Could not send via {app_name}: {exc}"


def send_message(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    receiver = str(p.get("receiver", "")).strip()
    message = str(p.get("message_text", "")).strip()
    platform = str(p.get("platform", "whatsapp")).strip().lower()
    attachment_path = str(p.get("attachment_path", "")).strip() or None

    if not receiver:
        return "Please specify a recipient."
    if not message and not attachment_path:
        return "Please specify the message content."
    if attachment_path:
        return "WhatsApp file attachments are not supported by the verified Chrome bridge yet. No message was sent."

    if platform in ("whatsapp", "whatsapp web", "wp", "wapp"):
        result = _whatsapp_web(receiver, message)
    else:
        result = _desktop_send(platform.title(), receiver, message)

    if player and hasattr(player, "write_log"):
        player.write_log("[message] " + result)
    return result


TOOL = {
    "name": "send_message",
    "description": (
        "Send WhatsApp messages through the user's existing Chrome session using "
        "the NOVA WhatsApp Bridge extension. It reuses an existing WhatsApp Web tab "
        "or opens one in the current Chrome window, waits for QR login, searches "
        "for an exact contact, verifies the chat header, then sends and confirms "
        "the message. Never launches a separate Chrome profile. Requires the "
        "NOVA WhatsApp Bridge extension to be installed and enabled."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {"type": "STRING", "description": "Exact WhatsApp contact name or number"},
            "message_text": {"type": "STRING", "description": "Exact message text to send"},
            "platform": {"type": "STRING", "description": "whatsapp | whatsapp web"},
            "attachment_path": {"type": "STRING", "description": "Optional attachment path (not supported)"},
        },
        "required": ["receiver", "message_text"],
    },
    "handler": send_message,
}
