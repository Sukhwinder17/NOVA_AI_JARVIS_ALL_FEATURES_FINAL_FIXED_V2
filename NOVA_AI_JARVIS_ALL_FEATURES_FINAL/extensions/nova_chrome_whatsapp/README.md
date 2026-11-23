# NOVA WhatsApp Chrome Bridge

This extension lets NOVA work with the Chrome session that is already open. It does not start a second Chrome profile and does not require remote-debugging flags.

## One-time setup

1. Start NOVA once after pulling the update. The local bridge listens only on 127.0.0.1:8765.
2. In the Chrome window you normally use, open `chrome://extensions`.
3. Turn on **Developer mode**.
4. Click **Load unpacked** and select:
   `NOVA_AI_JARVIS_ALL_FEATURES_FINAL/extensions/nova_chrome_whatsapp`
5. Make sure **NOVA WhatsApp Bridge** is enabled.
6. Reload the existing WhatsApp Web tab (web.whatsapp.com). If logged out, scan the QR code in that same tab.

## Use

Say: `Send WhatsApp message to Sahib saying Hello, this is a NOVA test.`

NOVA activates the existing WhatsApp tab, or opens WhatsApp Web as a new tab in the current Chrome window. It waits for login, requires an exact contact-name match and checks the chat header before sending.

The extension communicates only with NOVA's local loopback bridge. It does not send messages by itself; a send request must come from NOVA.
