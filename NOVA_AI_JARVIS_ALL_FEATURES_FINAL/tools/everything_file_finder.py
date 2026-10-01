from __future__ import annotations

import os
import re
import subprocess
import time
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


def _find_gui_exe(es_exe: Path) -> Path | None:
    candidates = [
        es_exe.with_name('Everything.exe'),
        es_exe.with_name('Everything64.exe'),
        Path(os.environ.get('ProgramFiles', '')) / 'Everything 1.5a' / 'Everything.exe',
        Path(os.environ.get('ProgramFiles', '')) / 'Everything 1.5a' / 'Everything64.exe',
        Path(os.environ.get('ProgramFiles', '')) / 'Everything' / 'Everything.exe',
        Path(os.environ.get('ProgramFiles', '')) / 'Everything' / 'Everything64.exe',
        Path(os.environ.get('ProgramFiles(x86)', '')) / 'Everything 1.5a' / 'Everything.exe',
        Path(os.environ.get('ProgramFiles(x86)', '')) / 'Everything 1.5a' / 'Everything64.exe',
        Path(os.environ.get('ProgramFiles(x86)', '')) / 'Everything' / 'Everything.exe',
        Path(os.environ.get('ProgramFiles(x86)', '')) / 'Everything' / 'Everything64.exe',
    ]
    for candidate in candidates:
        try:
            if candidate.exists(): return candidate
        except Exception: pass
    return None

def show_everything_search(query: str) -> bool:
    es_exe = Path(config.EVERYTHING_EXE)
    gui_exe = _find_gui_exe(es_exe)
    if not gui_exe: return False
    try:
        subprocess.Popen([str(gui_exe), '-search', query], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return True
    except Exception:
        return False

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

    def resolve_es_exe() -> Path:
        # Prefer the ES CLI installed with Everything. The bundled copy can be
        # an older/mismatched ES build that cannot talk to the running client.
        candidates = [
            Path(os.environ.get("ProgramFiles", "")) / "Everything 1.5a" / "es.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Everything" / "es.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Everything 1.5a" / "es.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Everything" / "es.exe",
            exe,
        ]
        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate
            except Exception:
                pass
        return exe

    es_cli = resolve_es_exe()

    def run_es(search_query: str, instance: str | None = None):
        try:
            args = [str(es_cli)]
            if instance:
                args += ["-instance", instance]
            # Use explicit -search and wait for the Everything database to be
            # ready. ES can otherwise return an empty result immediately after
            # Everything starts even though the GUI already shows the files.
            args += [
                "-n", str(limit),
                "/a-d",
                "-match-path",
                "-timeout", "10000",
                "-search", search_query,
            ]
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            stdout = result.stdout or ""
            return result.returncode, stdout
        except Exception:
            return -1, ""

    # Do NOT gate the search on config.EVERYTHING_EXE existing. The config
    # normally points to NOVA's bundled es.exe, while Everything may actually
    # be installed under Program Files\Everything 1.5a.
    if es_cli.exists():
        # Everything 1.5a uses a named IPC instance. Try it first, then the
        # unnamed instance for installations with alpha_instance disabled.
        for instance in ("1.5a", None):
            code, stdout = run_es(q, instance)
            if code == 0:
                raw = stdout.splitlines()
                if raw:
                    break

        # If Everything is not running, start it silently and retry.
        # -startup is documented to run Everything without opening a search window.
        if not raw:
            gui_exe = _find_gui_exe(es_cli)
            if gui_exe:
                try:
                    subprocess.Popen(
                        [str(gui_exe), "-startup", "-instance", "1.5a"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    time.sleep(2.5)
                    for instance in ("1.5a", None):
                        code, stdout = run_es(q, instance)
                        if code == 0:
                            raw = stdout.splitlines()
                            break
                except Exception:
                    pass

        # Intentionally no content search: NOVA's file finder is filename-only.

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