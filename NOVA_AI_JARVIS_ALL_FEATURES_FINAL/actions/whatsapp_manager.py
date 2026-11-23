from __future__ import annotations

import base64
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "whatsapp" / "scheduled.sqlite3"
API = os.getenv("NOVA_WPP_API_URL", "http://127.0.0.1:21465").rstrip("/")
SESSION = os.getenv("NOVA_WPP_SESSION", "nova")

_TIMEOUT = 35
_worker_started = False
_worker_lock = threading.Lock()


def _db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS scheduled (
        id TEXT PRIMARY KEY, recipient TEXT NOT NULL, message TEXT NOT NULL,
        send_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        result TEXT DEFAULT '', created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


def _request(method: str, endpoint: str, *, json=None, params=None):
    if not TOKEN:
        raise RuntimeError("WPPConnect is not configured. Set NOVA_WPP_TOKEN in .env after pairing.")
    url = f"{API}/api/{quote(SESSION, safe='')}/{endpoint.lstrip('/')}"
    response = requests.request(method, url, headers={"Authorization": f"Bearer {token}"}, json=json, params=params, timeout=_TIMEOUT)
    if not response.ok:
        raise RuntimeError(f"WPPConnect HTTP {response.status_code}: {response.text[:500]}")
    try:
        return response.json()
    except ValueError:
        return {"response": response.text}


def _normalise_phone(value: str) -> str:
    value = str(value or "").strip()
    if "@" in value:
        return value
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 7:
        raise ValueError("Use a WhatsApp number with country code, or an exact saved contact name.")
    return digits


def _contacts():
    data = _request("GET", "all-contacts")
    if isinstance(data, dict):
        data = data.get("response", data.get("contacts", []))
    return data if isinstance(data, list) else []


def _resolve_recipient(value: str) -> str:
    raw = value.strip()
    if "@" in raw or sum(ch.isdigit() for ch in raw) >= 7:
        return _normalise_phone(raw)
    matches = []
    for item in _contacts():
        name = str(item.get("name") or item.get("pushname") or item.get("formattedName") or "").strip()
        wid = item.get("id") or item.get("wid") or item.get("phone")
        if name.casefold() == raw.casefold() and wid:
            if isinstance(wid, dict):
                wid = wid.get("_serialized") or wid.get("user") or ""
            matches.append(str(wid))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Multiple contacts named '{raw}'. Use a phone number with country code.")
    raise ValueError(f"No exact WhatsApp contact named '{raw}' found. Try the number with country code.")


def _send_text(recipient: str, message: str):
    phone = _resolve_recipient(recipient)
    return _request("POST", "send-message", json={
        "phone": phone, "isGroup": phone.endswith("@g.us"),
        "isNewsletter": False, "isLid": False, "message": message,
    })


def _schedule_worker():
    while True:
        try:
            with _db() as conn:
                due = conn.execute("SELECT * FROM scheduled WHERE status='pending' AND send_at<=? ORDER BY send_at LIMIT 10", (datetime.now(timezone.utc).isoformat(),)).fetchall()
                for row in due:
                    conn.execute("UPDATE scheduled SET status='sending' WHERE id=?", (row["id"],))
                    conn.commit()
                    try:
                        _send_text(row["recipient"], row["message"])
                        conn.execute("UPDATE scheduled SET status='sent', result='Accepted by WPPConnect' WHERE id=?", (row["id"],))
                    except Exception as exc:
                        conn.execute("UPDATE scheduled SET status='failed', result=? WHERE id=?", (str(exc)[:1000], row["id"]))
                    conn.commit()
        except Exception as exc:
            print(f"[NOVA WhatsApp scheduler] {exc}")
        time.sleep(5)


def _start_worker():
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            threading.Thread(target=_schedule_worker, name="NOVA-WhatsApp-Scheduler", daemon=True).start()
            _worker_started = True


def whatsapp_manager(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    action = str(p.get("action", "status")).lower().strip()
    try:
        if action == "status":
            health = requests.get(f"{API}/healthz", timeout=5)
            if not health.ok:
                return f"WPPConnect server returned HTTP {health.status_code}."
            if not TOKEN:
                return "WPPConnect server is online, but NOVA_WPP_TOKEN is missing. Pair a session in Manager and add its session token to .env."
            return f"WPPConnect session status: {_request('GET', 'status-session')}"

        if action == "send":
            recipient, message = str(p.get("recipient", "")).strip(), str(p.get("message", "")).strip()
            if not recipient or not message:
                return "Provide recipient and message."
            result = _send_text(recipient, message)
            return f"WPPConnect accepted the message for {recipient}. Response: {result}"

        if action == "media":
            recipient = str(p.get("recipient", "")).strip()
            file_path = Path(str(p.get("file_path", "")).strip()).expanduser()
            if not recipient or not file_path.is_file():
                return "Provide a recipient and an existing file path."
            if file_path.stat().st_size > 15 * 1024 * 1024:
                return "File exceeds NOVA's 15 MB safety limit."
            phone = _resolve_recipient(recipient)
            result = _request("POST", "send-file", json={
                "phone": phone, "isGroup": phone.endswith("@g.us"),
                "isNewsletter": False, "isLid": False, "filename": file_path.name,
                "caption": str(p.get("caption", "")),
                "base64": base64.b64encode(file_path.read_bytes()).decode("ascii"),
            })
            return f"WPPConnect accepted {file_path.name} for {recipient}. Response: {result}"

        if action == "contacts":
            rows = []
            for item in _contacts()[:100]:
                name = item.get("name") or item.get("pushname") or item.get("formattedName") or "Unnamed"
                wid = item.get("id") or item.get("wid") or item.get("phone") or ""
                if isinstance(wid, dict):
                    wid = wid.get("_serialized") or wid.get("user") or ""
                rows.append(f"- {name}: {wid}")
            return "WhatsApp contacts (first 100):\n" + ("\n".join(rows) if rows else "No contacts returned.")

        if action == "inbox":
            return f"Unread WhatsApp messages: {_request('GET', 'all-unread-messages')}"

        if action == "schedule":
            recipient, message, send_at = (str(p.get(k, "")).strip() for k in ("recipient", "message", "send_at"))
            if not recipient or not message or not send_at:
                return "Provide recipient, message and send_at as an ISO date/time with timezone."
            target = datetime.fromisoformat(send_at.replace("Z", "+00:00"))
            if target.tzinfo is None or target <= datetime.now(timezone.utc):
                return "Scheduled time must include a timezone and be in the future."
            job_id = uuid.uuid4().hex[:12]
            with _db() as conn:
                conn.execute("INSERT INTO scheduled(id,recipient,message,send_at,status,created_at) VALUES(?,?,?,?,?,?)", (job_id, recipient, message, target.astimezone(timezone.utc).isoformat(), "pending", datetime.now(timezone.utc).isoformat()))
            _start_worker()
            return f"WhatsApp message scheduled (ID {job_id}) for {target.astimezone().strftime('%d %b %Y, %I:%M %p')} local time. NOVA must be running then."

        if action == "scheduled":
            with _db() as conn:
                rows = conn.execute("SELECT id,recipient,send_at,status,result FROM scheduled ORDER BY send_at DESC LIMIT 30").fetchall()
            return "\n".join(f"{r['id']} | {r['recipient']} | {r['send_at']} | {r['status']} {r['result']}" for r in rows) or "No scheduled WhatsApp messages."

        if action == "cancel":
            job_id = str(p.get("id", "")).strip()
            with _db() as conn:
                cur = conn.execute("UPDATE scheduled SET status='cancelled' WHERE id=? AND status='pending'", (job_id,))
            return "Scheduled WhatsApp message cancelled." if cur.rowcount else "No pending scheduled message found with that ID."

        return "Supported actions: status, send, media, contacts, inbox, schedule, scheduled, cancel."
    except Exception as exc:
        return f"WhatsApp {action} failed: {exc}"


TOOL = {
    "name": "whatsapp_manager",
    "description": "Manage NOVA's WPPConnect WhatsApp session. Actions: status, send (recipient,message), media (recipient,file_path,caption), contacts, inbox, schedule (recipient,message,send_at ISO timestamp with timezone), scheduled, cancel (id).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "enum": ["status", "send", "media", "contacts", "inbox", "schedule", "scheduled", "cancel"]},
            "recipient": {"type": "STRING"},
            "message": {"type": "STRING"},
            "file_path": {"type": "STRING"},
            "caption": {"type": "STRING"},
            "send_at": {"type": "STRING"},
            "id": {"type": "STRING"},
        },
        "required": ["action"],
    },
    "handler": whatsapp_manager,
}

# Resume persisted scheduled jobs whenever NOVA discovers this action at startup.
_start_worker()
