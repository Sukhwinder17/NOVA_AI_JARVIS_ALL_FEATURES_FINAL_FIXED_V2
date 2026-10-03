from __future__ import annotations

from core.phone_notification_server import read_notifications


def phone_notifications(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    limit = int(p.get("limit", 20) or 20)
    return read_notifications(max(1, min(limit, 100)))


TOOL = {
    "name": "phone_notifications",
    "description": "Read recent Android phone notifications received by the NOVA companion, including Messages/SMS and other forwarded notifications.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "limit": {"type": "INTEGER"},
        },
        "required": [],
    },
    "handler": phone_notifications,
}
