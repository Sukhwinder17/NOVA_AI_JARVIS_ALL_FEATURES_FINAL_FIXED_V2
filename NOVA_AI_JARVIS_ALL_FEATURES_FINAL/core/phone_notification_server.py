from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STORE = BASE / "data" / "phone" / "notifications.jsonl"
SMS_STORE = BASE / "data" / "phone" / "sms_status.jsonl"
HOST = "127.0.0.1"
PORT = 8765
_LOCK = threading.Lock()


def _save(item: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_notifications(limit: int = 20) -> str:
    if not STORE.exists():
        return "No phone notifications received yet."
    lines = STORE.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, limit):]
    items = []
    for line in lines:
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    if not items:
        return "No phone notifications received yet."
    out = ["📱 Recent phone notifications:"]
    for n in reversed(items):
        app = n.get("app") or n.get("package") or "Phone"
        title = n.get("title") or ""
        text = n.get("text") or ""
        when = n.get("time") or ""
        out.append(f"• {app}: {title} — {text} [{when}]")
    return "\n".join(out)


def read_sms_status(request_id: str) -> list[dict]:
    if not request_id or not SMS_STORE.exists():
        return []
    items = []
    for line in SMS_STORE.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        if str(item.get("request_id", "")) == request_id:
            items.append(item)
    return items


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/health":
            body = b'{"ok":true,"service":"NOVA phone notifications"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path not in ("/notification", "/sms_status"):
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            payload["time"] = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
            _save(payload, STORE if self.path == "/notification" else SMS_STORE)
            self.send_response(200)
            body = b'{"ok":true}'
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            self.send_response(400)
            self.end_headers()


class PhoneNotificationServer:
    def __init__(self):
        self._server = None
        self._thread = None

    def start(self):
        if self._server is not None:
            return
        try:
            self._server = ThreadingHTTPServer((HOST, PORT), _Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            print(f"[NOVA] Phone notification server listening on {HOST}:{PORT}")
        except OSError as exc:
            self._server = None
            print(f"[NOVA] Phone notification server unavailable: {exc}")

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
