from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_URL = "http://127.0.0.1:3000"
DEFAULT_SESSION = "nova"


def _read_env_file():
    if not ENV_PATH.exists():
        return {}
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def settings():
    file_values = _read_env_file()
    return {
        "url": os.getenv("NOVA_WAHA_URL") or file_values.get("NOVA_WAHA_URL") or DEFAULT_URL,
        "api_key": os.getenv("NOVA_WAHA_API_KEY") or file_values.get("NOVA_WAHA_API_KEY") or "",
        "session": os.getenv("NOVA_WAHA_SESSION") or file_values.get("NOVA_WAHA_SESSION") or DEFAULT_SESSION,
        "webhook_token": os.getenv("NOVA_WAHA_WEBHOOK_TOKEN") or file_values.get("NOVA_WAHA_WEBHOOK_TOKEN") or "",
        "dashboard_password": os.getenv("NOVA_WAHA_DASHBOARD_PASSWORD") or file_values.get("NOVA_WAHA_DASHBOARD_PASSWORD") or "",
    }


def save_settings(values):
    # Preserve comments and unrelated application settings in the user's .env.
    existing = ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines() if ENV_PATH.exists() else []
    keys = {
        "NOVA_WAHA_URL": str(values.get("url") or DEFAULT_URL).strip().rstrip("/"),
        "NOVA_WAHA_API_KEY": str(values.get("api_key") or "").strip(),
        "NOVA_WAHA_SESSION": str(values.get("session") or DEFAULT_SESSION).strip(),
        "NOVA_WAHA_WEBHOOK_TOKEN": str(values.get("webhook_token") or "").strip(),
        "NOVA_WAHA_DASHBOARD_PASSWORD": str(values.get("dashboard_password") or "").strip(),
    }
    found = set()
    output = []
    for line in existing:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in keys:
                output.append(f"{key}={keys[key]}")
                found.add(key)
                continue
        output.append(line)
    for key, value in keys.items():
        if key not in found:
            output.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(output) + "\n", encoding="utf-8")
    for key, value in keys.items():
        os.environ[key] = value
    return keys

def _request(method, endpoint, *, params=None, json=None, accept=None, timeout=20):
    cfg = settings()
    if not cfg["api_key"]:
        raise RuntimeError("NOVA_WAHA_API_KEY is empty. Save your WAHA API key in the WAHA Link tab first.")
    url = cfg["url"].rstrip("/") + endpoint
    headers = {"X-Api-Key": cfg["api_key"], "Accept": accept or "application/json"}
    if json is not None:
        headers["Content-Type"] = "application/json"
    try:
        response = requests.request(method, url, headers=headers, params=params, json=json, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Cannot reach WAHA at {cfg['url']}: {exc}") from exc
    if not response.ok:
        detail = response.text[:500]
        raise RuntimeError(f"WAHA returned HTTP {response.status_code}: {detail}")
    return response


def check_connection():
    response = _request("GET", "/api/sessions/")
    return response.json()


def create_or_start_session(webhook_url=None):
    cfg = settings()
    name = cfg["session"]
    webhooks = []
    if webhook_url and cfg["webhook_token"]:
        webhooks = [{
            "url": webhook_url,
            "events": ["message"],
            "customHeaders": [{"name": "X-NOVA-WAHA-TOKEN", "value": cfg["webhook_token"]}],
        }]
    sessions = check_connection()
    found = any((item.get("name") or item.get("session")) == name for item in sessions if isinstance(item, dict))
    if not found:
        body = {"name": name, "config": {"webhooks": webhooks}}
        response = _request("POST", "/api/sessions/", json=body)
        return response.json() if response.content else {"name": name, "status": "STARTING"}
    if webhooks:
        _request("POST", f"/api/sessions/{quote(name, safe='')}/", json={"config": {"webhooks": webhooks}})
    detail = _request("GET", f"/api/sessions/{quote(name, safe='')}").json()
    status = str(detail.get("status", "")).upper()
    if status not in ("WORKING", "SCAN_QR_CODE", "STARTING", "STARTED"):
        response = _request("POST", f"/api/sessions/{quote(name, safe='')}/start", json={})
        return response.json() if response.content else {"name": name, "status": "STARTING"}
    return detail


def get_qr_image():
    name = quote(settings()["session"], safe="")
    response = _request("GET", f"/api/{name}/auth/qr", accept="image/png")
    return response.content


def send_text(chat_id, text):
    chat_id = (chat_id or "").strip()
    text = (text or "").strip()
    if not chat_id or not text:
        raise ValueError("Enter a WhatsApp chat ID and message text.")
    response = _request("POST", "/api/sendText", json={
        "session": settings()["session"],
        "chatId": chat_id,
        "text": text,
    })
    return response.json() if response.content else {"success": True}
