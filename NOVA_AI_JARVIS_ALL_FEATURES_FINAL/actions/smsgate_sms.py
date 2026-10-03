from __future__ import annotations

from datetime import datetime

from core.smsgate_sms import cancel_message, read_messages, schedule_sms, send_sms


def smsgate_sms(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    action = str(p.get("action", "send")).strip().lower()

    if action in ("send", "immediate"):
        return send_sms(str(p.get("recipient", "")), str(p.get("message", "")))

    if action in ("schedule", "scheduled"):
        value = str(p.get("send_at", "")).strip()
        if not value:
            return "Please specify when the SMS should be sent."
        try:
            target = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return "Invalid SMS schedule time."
        return schedule_sms(str(p.get("recipient", "")), str(p.get("message", "")), target)

    if action in ("read", "inbox", "received"):
        return read_messages(int(p.get("limit", 20)))

    if action in ("cancel", "delete"):
        return cancel_message(str(p.get("message_id", "")))

    return "SMSGate actions: send, schedule, read, cancel."


TOOL = {
    "name": "smsgate_sms",
    "description": (
        "Send, receive, schedule, and cancel real SMS using the free/open-source SMS Gateway for Android public cloud. "
        "Messages are sent through the SIM in the registered Android phone. Scheduled messages use scheduleAt."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "send, schedule, read, or cancel"},
            "recipient": {"type": "STRING"},
            "message": {"type": "STRING"},
            "send_at": {"type": "STRING", "description": "ISO-8601 timestamp with timezone"},
            "message_id": {"type": "STRING"},
            "limit": {"type": "INTEGER"},
        },
        "required": ["action"],
    },
    "handler": smsgate_sms,
}
