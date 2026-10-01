from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from core import config

_last = []


def _clean(path):
    p = path.strip().strip('"')
    low = p.lower()

    if not p:
        return None

    # Remove noisy Windows Recent shortcuts
    if low.endswith(".lnk"):
        return None

    # Remove .git results
    if "\\.git\\" in low or low.endswith("\\.git") or "/.git/" in low:
        return None

    return p


def search(query: str, limit: int = 40):
    global _last

    exe = Path(config.EVERYTHING_EXE)

    if not exe.exists():
        return [], f"Everything CLI was not found at {exe}"

    # Clean natural-language commands
    q = query.strip()

    q = re.sub(
        r"\b(find|search|look for|show me|search for|files?|documents?|"
        r"folders?|file name|filename|related to|related|named|name|"
        r"on my (pc|computer|laptop)|my|the|all)\b",
        " ",
        q,
        flags=re.I,
    )

    q = re.sub(r"\s+", " ", q).strip()

    if not q:
        q = query.strip()

    try:
        # Use the same basic Everything command that was
        # verified to work from CMD.
        result = subprocess.run(
            [str(exe), q],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )

        raw = (result.stdout or "").splitlines()

    except Exception as e:
        return [], f"Everything search failed: {e}"

    out = []
    seen = set()

    for line in raw:
        p = _clean(line)

        if not p:
            continue

        key = p.lower()

        if key in seen:
            continue

        seen.add(key)
        out.append(p)

        if len(out) >= limit:
            break

    _last = out

    return out, q


def open_result(ref: str):
    ref = str(ref).strip()

    path = None

    # Open by result number
    if ref.isdigit():
        index = int(ref) - 1

        if 0 <= index < len(_last):
            path = _last[index]

    # Open by filename/path
    else:
        ref_lower = ref.lower()

        for p in _last:
            name = Path(p).name.lower()

            if ref_lower in name or ref_lower == p.lower():
                path = p
                break

    if not path:
        return "No matching recent file result."

    try:
        os.startfile(path)
        return f"Opened: {path}"

    except Exception as e:
        return f"Could not open {path}: {e}"