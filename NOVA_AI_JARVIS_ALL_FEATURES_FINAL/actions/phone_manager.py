from __future__ import annotations
from core.phone_manager import phone_command

def phone_manager(parameters: dict, player=None, **kwargs) -> str:
    p=parameters or {}
    action=str(p.get("action","status")).strip().lower()
    return phone_command(action, address=str(p.get("address","")), title=str(p.get("title","NOVA AI")), message=str(p.get("message","")), url=str(p.get("url","")))

TOOL={
    "name":"phone_manager",
    "description":"Connect NOVA to an Android phone over ADB, check connection and battery, send NOVA notifications, open URLs, take screenshots, and disconnect.",
    "parameters":{
        "type":"OBJECT",
        "properties":{
            "action":{"type":"STRING"},
            "address":{"type":"STRING"},
            "title":{"type":"STRING"},
            "message":{"type":"STRING"},
            "url":{"type":"STRING"}
        },
        "required":["action"]
    },
    "handler":phone_manager
}
