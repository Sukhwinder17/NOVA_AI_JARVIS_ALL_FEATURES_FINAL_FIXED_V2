from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_PATH = BASE_DIR / "memory" / "conversation_history.json"
MAX_MESSAGES = 120
_lock = Lock()


def load_history(limit: int = MAX_MESSAGES) -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    with _lock:
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    rows = []
    for item in data[-max(1, int(limit)):]:
        if isinstance(item, dict) and item.get("role") in ("user", "assistant"):
            rows.append({
                "role": item["role"],
                "content": str(item.get("content", "")),
                "time": str(item.get("time", "")),
            })
    return rows


def append_message(role: str, content: str) -> None:
    if role not in ("user", "assistant"):
        return
    content = str(content or "").strip()
    if not content:
        return
    with _lock:
        rows = load_history(MAX_MESSAGES)
        rows.append({
            "role": role,
            "content": content[:12000],
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(
            json.dumps(rows[-MAX_MESSAGES:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def clear_history() -> None:
    with _lock:
        if HISTORY_PATH.exists():
            HISTORY_PATH.unlink()
