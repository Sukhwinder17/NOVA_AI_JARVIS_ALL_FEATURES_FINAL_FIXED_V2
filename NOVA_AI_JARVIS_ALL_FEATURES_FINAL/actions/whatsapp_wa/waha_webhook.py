from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request

from .store import connect

app = FastAPI(title="NOVA WA Local WAHA Receiver")


def _expected_token():
    from .waha_client import settings
    return settings()["webhook_token"]


@app.get("/health")
def health():
    return {"status": "ok", "service": "nova-waha-receiver"}


@app.post("/waha/events")
async def receive_waha_event(request: Request, x_nova_waha_token: str = Header(default="")):
    token = _expected_token()
    if not token or not hmac.compare_digest(token, x_nova_waha_token):
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    event = await request.json()
    if event.get("event") != "message":
        return {"ignored": True, "reason": "unsupported event"}
    payload = event.get("payload") or {}
    if payload.get("fromMe") is True:
        return {"ignored": True, "reason": "outgoing message"}
    text = str(payload.get("body") or payload.get("text") or "").strip()
    if not text:
        return {"ignored": True, "reason": "message has no text"}
    chat_id = str(payload.get("from") or payload.get("chatId") or "").strip()
    if not chat_id:
        return {"ignored": True, "reason": "missing chat id"}
    external_id = str((payload.get("id") or {}).get("_serialized") if isinstance(payload.get("id"), dict) else payload.get("id") or "")
    if not external_id:
        external_id = hashlib.sha256(f"{chat_id}|{payload.get('timestamp')}|{text}".encode("utf-8")).hexdigest()
    timestamp = payload.get("timestamp")
    try:
        if isinstance(timestamp, (int, float)):
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            stamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()
        else:
            stamp = datetime.now().astimezone().isoformat()
    except (ValueError, OSError, OverflowError):
        stamp = datetime.now().astimezone().isoformat()

    sender = str(payload.get("pushName") or payload.get("notifyName") or chat_id)
    digest = hashlib.sha256(("waha:" + external_id).encode("utf-8")).hexdigest()
    title = chat_id
    with connect() as db:
        cur = db.execute(
            "INSERT OR IGNORE INTO imports(source_name,source_type,content_sha256,message_count) VALUES(?,?,?,1)",
            (f"WAHA live message {external_id}", "waha_live", digest),
        )
        if cur.rowcount == 0:
            return {"duplicate": True}
        import_id = cur.lastrowid
        db.execute("INSERT OR IGNORE INTO contacts(display_name) VALUES(?)", (title,))
        contact_id = db.execute("SELECT id FROM contacts WHERE display_name=?", (title,)).fetchone()[0]
        conv = db.execute(
            "INSERT INTO conversations(contact_id,import_id,title,source_type) VALUES(?,?,?,'waha_live')",
            (contact_id, import_id, title),
        )
        db.execute(
            "INSERT INTO messages(conversation_id,external_id,timestamp,sender,text,message_type) VALUES(?,?,?,?,?,'text')",
            (conv.lastrowid, external_id, stamp, sender, text),
        )
    return {"stored": True, "message_id": external_id}
