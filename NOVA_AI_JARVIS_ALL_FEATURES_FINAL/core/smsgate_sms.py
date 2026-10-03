from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests

BASE_URL = os.getenv("SMSGATE_BASE_URL", "https://api.sms-gate.app/3rdparty/v1").rstrip("/")
LOGIN = os.getenv("SMSGATE_LOGIN", "").strip()
PASSWORD = os.getenv("SMSGATE_PASSWORD", "").strip()


def configured() -> bool:
    return bool(LOGIN and PASSWORD)


def _number(value: str) -> str:
    raw = str(value or "").strip()
    cleaned = re.sub(r"[^0-9+]", "", raw)
    if not cleaned or cleaned.startswith("++") or ("+" in cleaned[1:]):
        raise ValueError("Please provide a valid SMS phone number.")
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 7:
        raise ValueError("Please provide a valid SMS phone number.")
    return cleaned if cleaned.startswith("+") else "+" + digits


def _request(method: str, path: str, **kwargs):
    if not configured():
        raise RuntimeError("SMSGate is not configured. Set SMSGATE_LOGIN and SMSGATE_PASSWORD in .env.")

    response = requests.request(
        method,
        f"{BASE_URL}/{path.lstrip('/')}",
        auth=(LOGIN, PASSWORD),
        timeout=25,
        **kwargs,
    )

    if not response.ok:
        try:
            payload = response.json()
            detail = payload.get("message") or payload
        except Exception:
            detail = response.text or f"HTTP {response.status_code}"
        raise RuntimeError(f"SMSGate HTTP {response.status_code}: {detail}")

    try:
        return response.json()
    except Exception:
        return {}


def send_sms(recipient: str, message: str) -> str:
    try:
        to = _number(recipient)
    except ValueError as exc:
        return str(exc)

    body = str(message or "").strip()
    if not body:
        return "Please provide the SMS message."

    try:
        data = _request(
            "POST",
            "/messages",
            json={
                "textMessage": {"text": body},
                "phoneNumbers": [to],
                "withDeliveryReport": True,
            },
        )
    except Exception as exc:
        return f"Could not send SMS through SMSGate: {exc}"

    mid = data.get("id") or data.get("messageId") or data.get("smsId") or ""
    state = data.get("state") or data.get("status") or "Queued"
    suffix = f" Message ID: {mid}." if mid else ""
    return f"📨 SMS submitted through SMSGate to {to}. Status: {state}.{suffix}"


def schedule_sms(recipient: str, message: str, send_at: datetime) -> str:
    try:
        to = _number(recipient)
    except ValueError as exc:
        return str(exc)

    body = str(message or "").strip()
    if not body:
        return "Please provide the SMS message."

    if send_at.tzinfo is None:
        send_at = send_at.astimezone()

    send_at = send_at.astimezone(timezone.utc)
    if send_at <= datetime.now(timezone.utc):
        return "The scheduled time must be in the future."

    try:
        data = _request(
            "POST",
            "/messages",
            json={
                "textMessage": {"text": body},
                "phoneNumbers": [to],
                "scheduleAt": send_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "withDeliveryReport": True,
            },
        )
    except Exception as exc:
        return f"Could not schedule SMS through SMSGate: {exc}"

    mid = data.get("id") or data.get("messageId") or data.get("smsId") or ""
    state = data.get("state") or data.get("status") or "Pending"
    local_time = send_at.astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z")
    suffix = f" Message ID: {mid}." if mid else ""
    return (
        f"⏰ SMS scheduled through SMSGate for {local_time} to {to}. "
        f"The laptop does not need to stay connected. Status: {state}.{suffix}"
    )


def read_messages(limit: int = 20) -> str:
    try:
        data = _request(
            "GET",
            "/messages",
            params={
                "direction": "received",
                "order": "desc",
                "limit": max(1, min(int(limit), 100)),
            },
        )
    except Exception as exc:
        return f"Could not read SMS through SMSGate: {exc}"

    items = data.get("data") if isinstance(data, dict) else None
    if not items:
        return "No received SMS messages found in SMSGate."

    lines = ["📱 Recent SMS messages:"]
    for item in items:
        sender = item.get("sender") or item.get("phoneNumber") or "Unknown"
        text = item.get("message") or item.get("text") or ""
        when = item.get("receivedAt") or item.get("createdAt") or ""
        lines.append(f"• {sender}: {text} [{when}]")
    return "\n".join(lines)


def cancel_message(message_id: str) -> str:
    mid = str(message_id or "").strip()
    if not mid:
        return "Please provide the SMS message ID to cancel."

    try:
        data = _request("DELETE", f"/messages/{mid}")
    except Exception as exc:
        return f"Could not cancel SMS through SMSGate: {exc}"

    state = data.get("state") or data.get("status") or "Cancellation requested"
    return f"🗑️ SMS cancellation requested for {mid}. Status: {state}."
