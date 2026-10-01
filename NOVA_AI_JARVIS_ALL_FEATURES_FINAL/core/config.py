from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
load_dotenv()

APP_NAME = os.getenv('APP_NAME', 'NOVA AI').strip() or 'NOVA AI'
AI_PROVIDER = os.getenv('AI_PROVIDER', 'auto').strip().lower()

GROQ_API_KEY = os.getenv('GROQ_API_KEY', '').strip()
GROQ_BASE_URL = os.getenv('GROQ_BASE_URL', 'https://api.groq.com/openai/v1').strip()
GROQ_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-120b').strip()
GROQ_VISION_MODEL = os.getenv('GROQ_VISION_MODEL', 'qwen/qwen3.8-27b').strip()
GROQ_STT_MODEL = os.getenv('GROQ_STT_MODEL', 'whisper-large-v3-turbo').strip()

XKIRO_API_KEY = os.getenv('XKIRO_API_KEY', '').strip()
XKIRO_BASE_URL = os.getenv('XKIRO_BASE_URL', 'https://api.xkiro.com/v1').strip()
XKIRO_MODEL = os.getenv('XKIRO_MODEL', 'mistralai/mistral-large-2512').strip()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '').strip()
GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta/openai/').strip()
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip()

DATALENS_URL = os.getenv('DATALENS_URL', 'https://frontend-liard-rho-s59bfvv4uq.vercel.app').strip()
EVERYTHING_EXE = os.getenv('EVERYTHING_EXE', str(BASE_DIR / 'tools' / 'bin' / 'es.exe')).strip()
NOVA_BROWSER_PROFILE = os.getenv('NOVA_BROWSER_PROFILE', str(BASE_DIR / 'data' / 'browser_profile')).strip()
WHATSAPP_URL = os.getenv('WHATSAPP_URL', 'https://web.whatsapp.com').strip()

TTS_VOICE = os.getenv('NOVA_TTS_VOICE', 'David').strip()
TTS_RATE = int(os.getenv('NOVA_TTS_RATE', '180') or 180)

# Compatibility file for Mark-LV actions that still read config/api_keys.json.
# It contains the local Gemini key only; the file is gitignored.
def sync_legacy_config() -> None:
    import json
    path = BASE_DIR / 'config' / 'api_keys.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            data = {}
    if GEMINI_API_KEY:
        data['gemini_api_key'] = GEMINI_API_KEY
    data['os_system'] = 'windows' if os.name == 'nt' else ('mac' if os.uname().sysname == 'Darwin' else 'linux')
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
