# NOVA WA — WAHA Link (Windows)

This adds a local WAHA connector to NOVA WA. It starts WAHA through Docker Compose, creates/starts a persistent session, displays the pairing QR, and supports deliberate manual text sends. Incoming text messages can be forwarded to NOVA's local receiver and saved into the NOVA WA SQLite database.

## Important account note

WAHA uses an unofficial WhatsApp linked-device integration, not the official WhatsApp Business Cloud API. WhatsApp may change or restrict unofficial clients/accounts. Use a secondary number for testing if possible. Connecting the session is an explicit action in the NOVA UI; automatic replies are not enabled by this connector.

## Quick setup

1. Ensure Docker Desktop is installed and running.
2. Open NOVA WA and select **WAHA Link**.
3. Click **Generate keys / Save settings**. NOVA creates strong local API, dashboard and webhook keys and writes them to the project `.env`. Keep that file private.
4. Click **Start WAHA (Docker)**. On first launch, Docker downloads the WAHA image; this may take a few minutes.
5. Click **Check connection**.
6. Click **Start / Link WhatsApp**, accept the warning, then wait a few seconds and click **Refresh QR** if the QR is not ready.
7. On your phone, open WhatsApp → **Linked devices** → **Link a device**, then scan the QR displayed in NOVA.
8. The session data is persisted in `.sessions/`; it should not require scanning again after ordinary restarts.

## Incoming messages

NOVA starts a local receiver on port 8788 and configures WAHA to send message events to `host.docker.internal`. The receiver validates a private webhook token and stores incoming text messages in `data/whatsapp_wa/nova_wa.sqlite3`. Refresh NOVA WA's dashboard/modules to see newly received messages, The WAHA Link tab also has **Sync recent chats into NOVA**: it imports up to 20 recent chats and 30 text messages per chat. It deduplicates message IDs and does not download media. Run NOVA's analysis afterward if desired.

The receiver binds to the host interfaces so the Docker container can reach it. The webhook token is required; do not expose port 8788 to the internet or share the token.

## Manual sending

Enter a chat ID such as `9198XXXXXXXX@c.us`, type the message, and click **Send this message**. NOVA asks for confirmation before sending. This is not an auto-reply engine.

## Local services and data

- WAHA API: `http://127.0.0.1:3000`
- WAHA Dashboard: `http://127.0.0.1:3000/dashboard` (use username `admin` and the generated dashboard password)
- WAHA session/media data: `.sessions/`, `.media/`
- NOVA incoming receiver: `http://127.0.0.1:8788/health`
- NOVA WA database: `data/whatsapp_wa/nova_wa.sqlite3`

Stop WAHA from the project directory with:

```powershell
docker compose -f docker-compose.waha.yml down
```

To unlink the account completely, use WhatsApp on your phone → Linked devices → select the WAHA device → Log out. Stopping the Docker container alone does not necessarily unlink the device.
