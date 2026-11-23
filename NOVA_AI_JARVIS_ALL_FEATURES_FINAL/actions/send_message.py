from __future__ import annotations

def send_message(parameters: dict, player=None, **kwargs) -> str:
    p = parameters or {}
    platform = str(p.get("platform", "whatsapp")).strip().lower()
    if platform not in ("whatsapp", "whatsapp web", "wp", "wapp"):
        return "This NOVA integration currently supports WhatsApp. Other messaging platforms need their own configured provider."
    from actions.whatsapp_manager import whatsapp_manager
    return whatsapp_manager({
        "action": "send",
        "recipient": p.get("receiver", ""),
        "message": p.get("message_text", ""),
    }, player=player)


TOOL = {
    "name": "send_message",
    "description": "Send an explicitly requested WhatsApp message through NOVA's separate WPPConnect session. Accepts an exact contact name or phone number with country code and the message text. Requires a paired WPPConnect session configured in NOVA .env.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {"type": "STRING", "description": "Exact WhatsApp contact name or phone number with country code"},
            "message_text": {"type": "STRING", "description": "Exact message text"},
            "platform": {"type": "STRING", "description": "whatsapp"},
        },
        "required": ["receiver", "message_text"],
    },
    "handler": send_message,
}
