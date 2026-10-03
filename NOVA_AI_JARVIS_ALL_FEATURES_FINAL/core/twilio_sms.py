from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "").strip()
TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/"


def configured() -> bool:
    return bool(
        TWILIO_ACCOUNT_SID
        and TWILIO_AUTH_TOKEN
        and TWILIO_MESSAGING_SERVICE_SID
    )


def _normalize_number(value: str) -> str:
    raw = str(value or "").strip()
    cleaned = re.sub(r"[^0-9+]", "", raw)
    if not cleaned or cleaned.startswith("++") or ("+" in cleaned[1:]):
        raise ValueError("Please provide a valid SMS phone number.")
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 7:
        raise ValueError("Please provide a valid SMS phone number.")
    # Twilio accepts E.164 numbers. Require a leading + for predictable routing.
    if not cleaned.startswith("+"):
        cleaned = "+" + digits
    return cleaned


def schedule_sms(
    recipient: str,
    message: str,
    send_at: datetime,
) -> str:
    if not configured():
        return (
            "Twilio is not configured yet. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, and TWILIO_MESSAGING_SERVICE_SID in NOVA's .env file."
        )

    try:
        to = _normalize_number(recipient)
    except ValueError as exc:
        return str(exc)

    body = str(message or "").strip()
    if not body:
        return "Please provide the SMS message."

    if send_at.tzinfo is None:
        send_at = send_at.astimezone()
    send_at_utc = send_at.astimezone(timezone.utc)

    now = datetime.now(timezone.utc)
    seconds = (send_at_utc - now).total_seconds()
    if seconds < 15 * 60:
        return (
            "Twilio scheduled SMS requires the request to be submitted at least "
            "15 minutes before the send time. Please choose a time at least 15 minutes ahead."
        )
    if seconds > 35 * 24 * 60 * 60:
        return "Twilio scheduled SMS can be set up to 35 days ahead."

    url = urljoin(TWILIO_API_BASE, f"Accounts/{TWILIO_ACCOUNT_SID}/Messages.json")
    data = {
        "To": to,
        "Body": body,
        "MessagingServiceSid": TWILIO_MESSAGING_SERVICE_SID,
        "ScheduleType": "fixed",
        "SendAt": send_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        response = requests.post(
            url,
            data=data,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=25,
        )
    except requests.RequestException as exc:
        return f"Twilio connection failed: {exc}"

    if not response.ok:
        try:
            detail = response.json()
            code = detail.get("code")
            msg = detail.get("message") or response.text
            if code:
                return f"Twilio rejected the scheduled SMS ({code}): {msg}"
            return f"Twilio rejected the scheduled SMS: {msg}"
        except Exception:
            return f"Twilio rejected the scheduled SMS: HTTP {response.status_code}"

    try:
        result = response.json()
        sid = result.get("sid", "")
        status = result.get("status", "queued")
        when = send_at.astimezone().strftime("%Y-%m-%d %I:%M %p %Z")
        return (
            f"✅ SMS scheduled through Twilio for {when} to {to}. "
            f"Twilio status: {status}."
            + (f" Message SID: {sid}." if sid else "")
            + " Your laptop and Vivo do not need to stay connected."
        )
    except Exception:
        when = send_at.astimezone().strftime("%Y-%m-%d %I:%M %p %Z")
        return f"✅ SMS scheduled through Twilio for {when} to {to}. Your laptop and Vivo do not need to stay connected."
