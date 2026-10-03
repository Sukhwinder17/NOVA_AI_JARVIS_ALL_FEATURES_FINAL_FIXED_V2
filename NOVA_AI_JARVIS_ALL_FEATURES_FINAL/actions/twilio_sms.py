from __future__ import annotations

from datetime import datetime

from core.twilio_sms import schedule_sms


def twilio_sms(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    recipient = str(p.get("recipient", "")).strip()
    message = str(p.get("message", "")).strip()
    send_at_iso = str(p.get("send_at", "")).strip()

    if not recipient:
        return "Please specify the SMS recipient phone number."
    if not message:
        return "Please specify the SMS message."
    if not send_at_iso:
        return "Please specify when the SMS should be sent."

    try:
        send_at = datetime.fromisoformat(send_at_iso.replace("Z", "+00:00"))
    except ValueError:
        return "Invalid SMS schedule time."

    return schedule_sms(recipient, message, send_at)


TOOL = {
    "name": "twilio_sms",
    "description": (
        "Schedule a real SMS through Twilio Messaging. Use for future SMS delivery "
        "when the laptop and Vivo should not need to remain connected. Twilio requires "
        "a Messaging Service SID and accepts fixed schedules 15 minutes to 35 days ahead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "recipient": {"type": "STRING", "description": "SMS recipient phone number"},
            "message": {"type": "STRING", "description": "Complete SMS body"},
            "send_at": {"type": "STRING", "description": "ISO-8601 send time with timezone, e.g. 2026-10-03T13:00:00+05:30"},
        },
        "required": ["recipient", "message", "send_at"],
    },
    "handler": twilio_sms,
}
