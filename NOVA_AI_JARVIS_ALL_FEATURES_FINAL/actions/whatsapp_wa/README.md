# NOVA WA foundation

This module separates personal WhatsApp manual imports from a separate official WhatsApp Business Cloud API channel. It never logs into or automates a personal WhatsApp account.

## Personal chat import
Import WhatsApp-exported .txt files or paste selected messages. Data is stored locally in data/whatsapp_wa/nova_wa.sqlite3. Imports are SHA-256 deduplicated and searchable with SQLite FTS5. First-pass task, commitment and risk indicators are heuristic suggestions, not confirmed facts or definitive scam verdicts.

## Business API configuration
Set these values in the local .env only:
- NOVA_WA_ACCESS_TOKEN
- NOVA_WA_PHONE_NUMBER_ID
- NOVA_WA_APP_SECRET
- NOVA_WA_VERIFY_TOKEN
- NOVA_WA_AUTOMATION_ENABLED=false
- NOVA_WA_MIN_CONFIDENCE=0.82
- NOVA_WA_GRAPH_VERSION=v23.0

Run local webhook development with: uvicorn actions.whatsapp_wa.webhook:app --host 127.0.0.1 --port 8787
Meta requires a public HTTPS webhook endpoint for production. Secure it and verify signatures. Do not expose the local development server directly.

This foundation persists verified webhook events and provides an official API send adapter. Automatic AI reply generation is not enabled yet: model integration, allowlist UI, confidence policy, opt-in and end-to-end testing are required before enabling outbound automation.
