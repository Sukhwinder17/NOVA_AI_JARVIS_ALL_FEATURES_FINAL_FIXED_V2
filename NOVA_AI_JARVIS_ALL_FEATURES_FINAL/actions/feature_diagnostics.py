from __future__ import annotations

from pathlib import Path
import importlib
from core import config


def feature_diagnostics(parameters=None, player=None, **kwargs):
    checks = []

    checks.append(("Groq API", bool(config.GROQ_API_KEY), "API key configured" if config.GROQ_API_KEY else "missing API key"))
    checks.append(("xKiro API", bool(config.XKIRO_API_KEY), "API key configured" if config.XKIRO_API_KEY else "missing API key"))
    checks.append(("Gemini API", bool(config.GEMINI_API_KEY), "API key configured" if config.GEMINI_API_KEY else "missing API key"))

    es = Path(config.EVERYTHING_EXE)
    checks.append(("Everything", es.exists(), str(es)))

    for mod in ("playwright", "pyautogui", "sounddevice", "soundfile", "ddgs"):
        try:
            importlib.import_module(mod)
            checks.append((mod, True, "installed"))
        except Exception as exc:
            checks.append((mod, False, str(exc)))

    checks.append(("DataLens", bool(config.DATALENS_URL), config.DATALENS_URL))
    checks.append(("WhatsApp", bool(config.WHATSAPP_URL), config.WHATSAPP_URL))
    checks.append((
        "SMSGate",
        bool(getattr(config, "SMSGATE_LOGIN", "")) and bool(getattr(config, "SMSGATE_PASSWORD", "")),
        "Cloud credentials configured"
        if getattr(config, "SMSGATE_LOGIN", "") and getattr(config, "SMSGATE_PASSWORD", "")
        else "missing SMSGATE_LOGIN/SMSGATE_PASSWORD",
    ))

    ok = sum(1 for _, good, _ in checks if good)
    lines = [f"NOVA feature check: {ok}/{len(checks)} core checks ready"]
    for name, good, detail in checks:
        lines.append(f"{'OK' if good else 'ISSUE'}  {name}: {detail}")

    result = "\n".join(lines)
    if player and hasattr(player, "write_log"):
        player.write_log("[diagnostics] " + result)
    return result


TOOL = {
    "name": "feature_diagnostics",
    "description": "Runs a safe NOVA capability health check for APIs, Everything, Playwright, voice packages, web-search fallback, DataLens and WhatsApp configuration. Use when the user asks to check/test/diagnose NOVA features.",
    "parameters": {"type": "OBJECT", "properties": {}},
    "handler": feature_diagnostics,
}
