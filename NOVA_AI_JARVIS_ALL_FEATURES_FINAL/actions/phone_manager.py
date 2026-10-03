from __future__ import annotations

from core.phone_manager import phone_command

def phone_manager(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    action = str(p.get("action", "status")).strip().lower()
    return phone_command(
        action,
        address=str(p.get("address", "")),
        title=str(p.get("title", "NOVA AI")),
        message=str(p.get("message", "")),
        recipient=str(p.get("recipient", "")),
        number=str(p.get("number", "")),
        url=str(p.get("url", "")),
        app=str(p.get("app", "")),
        text=str(p.get("text", "")),
        direction=str(p.get("direction", "")),
        media_action=str(p.get("media_action", "")),
    )

TOOL = {
    "name": "phone_manager",
    "description": (
        "Control a connected Android phone over wireless or USB ADB: connect, "
        "battery/status, device info, notifications, background SMS sending, open URLs, "
        "launch common apps, phone screenshots, clipboard read/write, volume controls, "
        "media controls, and disconnect. For SMS, open the phone's native Messages "
        "composer with the recipient and exact message filled in; the user taps Send."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING"},
            "address": {"type": "STRING"},
            "title": {"type": "STRING"},
            "message": {"type": "STRING"},
            "recipient": {"type": "STRING", "description": "SMS recipient phone number"},
            "number": {"type": "STRING", "description": "Alias for SMS recipient phone number"},
            "url": {"type": "STRING"},
            "app": {"type": "STRING"},
            "text": {"type": "STRING"},
            "direction": {"type": "STRING"},
            "media_action": {"type": "STRING"},
        },
        "required": ["action"],
    },
    "handler": phone_manager,
}
