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


def _fallback_search(query: str, limit: int = 40) -> list[str]:
    terms = [w.lower() for w in query.split() if w]
    found = []
    seen = set()

    search_roots = [
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.cwd(),
    ]

    for root in search_roots:
        if not root.exists():
            continue
        try:
            # Walk top-level and subdirectories (depth 3)
            for path in root.rglob("*"):
                if path.is_file():
                    name_lower = path.name.lower()
                    if all(term in name_lower for term in terms):
                        full_str = str(path.resolve())
                        if full_str.lower() not in seen:
                            seen.add(full_str.lower())
                            found.append(full_str)
                            if len(found) >= limit:
                                return found
        except Exception:
            continue
    return found


def search(query: str, limit: int = 40):
    global _last

    exe = Path(config.EVERYTHING_EXE)

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

    raw = []
    if exe.exists():
        try:
            result = subprocess.run(
                [str(exe), q],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            stdout = result.stdout or ""
            if result.returncode == 0 and "IPC not found" not in stdout and "Error" not in stdout:
                raw = stdout.splitlines()
        except Exception:
            pass

    if not raw:
        raw = _fallback_search(q, limit=limit)

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