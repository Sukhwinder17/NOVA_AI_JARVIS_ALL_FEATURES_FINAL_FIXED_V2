# NOVA WhatsApp — WPPConnect setup

NOVA uses a separate WPPConnect Server session. It does not use the NOVA Chrome extension or port 8766. The server is bound to 127.0.0.1:21465.

## Requirements

- Docker Desktop installed and running (WSL 2 backend recommended).
- NOVA's existing Python environment; requests is already in requirements.txt.
- A WhatsApp account you own or are authorized to operate.

## Configure and start the server

In the NOVA project root, use PowerShell to generate a strong local secret and add it to the existing .env file:

~~~powershell
$secret = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(36))
Add-Content .env "WPP_SECRET_KEY=$secret"
~~~

Do not share or commit this secret. Start WPPConnect:

~~~powershell
docker compose --env-file .env -f docker-compose.whatsapp.yml up -d
docker compose -f docker-compose.whatsapp.yml ps
Invoke-RestMethod http://127.0.0.1:21465/healthz
~~~

## Pair WhatsApp

1. Open http://127.0.0.1:21465/manager/ in Chrome.
2. Sign in using WPP_SECRET_KEY from your local .env.
3. Create a session named nova and start it.
4. Scan its QR code using WhatsApp > Linked devices.
5. Wait until the session status shows CONNECTED.
6. Copy the session API token from the session details. Do not use the server secret as the session token.

Add these settings to the existing NOVA .env. Preserve all other API keys and settings:

~~~dotenv
NOVA_WPP_API_URL=http://127.0.0.1:21465
NOVA_WPP_SESSION=nova
NOVA_WPP_TOKEN=PASTE_SESSION_TOKEN_HERE
~~~

Restart NOVA after changing .env.

## Supported NOVA actions

- whatsapp status
- show my WhatsApp contacts
- read my WhatsApp messages
- send WhatsApp message to +91XXXXXXXXXX saying Hello
- WhatsApp manager media action with recipient, file_path and optional caption
- WhatsApp manager schedule action with recipient, message and send_at (ISO timestamp including timezone)
- show scheduled WhatsApp messages
- cancel scheduled WhatsApp message by ID

The new whatsapp_manager tool exposes status, send, media, contacts, inbox, schedule, scheduled and cancel actions. Text sending remains available through NOVA's existing send_message action.

Scheduled messages are stored in a local SQLite database. NOVA must be running at the scheduled time for the in-process scheduler to dispatch them. If NOVA is closed or the computer is off, the job remains pending and will be attempted when NOVA next starts.

## Security and operational notes

- Keep port 21465 bound to 127.0.0.1. Do not expose it to the internet.
- Keep .env, WPPConnect token volumes and WhatsApp session data private.
- Send only messages explicitly requested by the user; avoid unsolicited or bulk messaging.
- WPPConnect is an unofficial WhatsApp Web automation project, independent of Meta/WhatsApp. WhatsApp Web changes may affect compatibility and use may be subject to platform restrictions.
- The previous Chrome extension bridge is retained for rollback but is no longer used by the send_message action.
