# NOVA AI — Native Desktop Edition

NOVA is a native Windows desktop assistant. It is not Streamlit and it does not use a sidebar as the primary interaction model.

The interface is built around one animated reactor sphere, a persistent conversation, and natural-language commands. The assistant can use Groq by default, xKiro as fallback, and Gemini when explicitly selected.

## What was integrated from the uploaded Mark-LV / JARVIS source

The uploaded Mark-LV project contains the real action architecture rather than a static demo. NOVA keeps that action architecture and wires it into a Groq/xKiro/Gemini tool-calling router.

Included capabilities include:

- native desktop UI with animated NOVA sphere
- persistent chat history
- Groq / xKiro / Gemini provider routing
- whole-PC Everything file search with numbered results and `open 1`
- real application launching
- real browser launching and browser automation
- ChatGPT Chat Fusion: import an export ZIP or `conversations.json`, select multiple chats, merge their messages chronologically, and continue asking NOVA questions grounded in the combined context
- YouTube control and video playback actions
- desktop and computer controls
- file management and file processing
- code writing, editing, running and project-building agent
- web search / news / research / price / compare
- weather and flight lookup actions
- reminders
- memory and recall
- undo support
- background monitoring
- system telemetry
- screen vision using Groq vision
- webcam vision using Groq vision
- clipboard intelligence
- invoice template rendering
- plugin discovery architecture
- remote dashboard source from Mark-LV
- wake-word source from Mark-LV
- audio-device source from Mark-LV
- native TTS and one-exchange voice input
- optional push-to-talk with Ctrl+Space

The human-face avatar was intentionally removed. The visual identity is NOVA's animated sphere.

## Setup on Windows

1. Extract this folder.
2. Copy your existing `.env` from your working NOVA project into this folder. Do not paste API keys into chat.
3. Put Everything CLI at:

   `tools\\bin\\es.exe`

4. Open CMD in the folder and run:

   `python -m venv venv`

   `venv\\Scripts\\activate`

   `python -m pip install --upgrade pip`

   `python -m pip install -r requirements.txt`

5. Install Playwright's browser runtime once:

   `python -m playwright install chromium`

6. Start NOVA:

   `python main.py`

Or double-click `START_NOVA_AI.bat`.


## Gmail one-message connection

NOVA supports passwordless Gmail connection through Google's OAuth browser flow. The user does not type a Gmail password into NOVA.

1. In Google Cloud, create an OAuth Client ID of type **Desktop app** and download the JSON.
2. Rename the downloaded file to `google_credentials.json`.
3. Put it at `config\google_credentials.json` (the file is gitignored).
4. Start NOVA and send exactly: `connect email`.
5. NOVA opens Google's account chooser/sign-in page. Complete Google sign-in and consent once.
6. NOVA stores the OAuth token locally under `data\gmail_tokens_v2\` and can reuse it on later launches.

The repository includes `config/google_credentials.example.json` only as a safe format example. **Never commit the real client secret JSON.** If a real client-secret file is ever uploaded to chat, pasted publicly, or committed, revoke/rotate that OAuth client secret in Google Cloud before continuing.

Gmail OAuth in this build requests Gmail modify + send permissions so the integration can be extended from inbox reading to actions such as sending/replying and message organization.
## ChatGPT Chat Fusion

Open **CHAT FUSION** from NOVA's main window. Import a ChatGPT data export ZIP or `conversations.json`, select at least two conversations, and choose **Merge selected conversations**. NOVA builds a chronological, source-labeled context and lets you continue asking questions using the selected chats. The merged transcript can be exported as a new text file. Original chats are not modified. Chat Fusion uses the selected NOVA AI provider and does not execute tools based on imported conversation text.

## First tests

Type these one at a time:

- `open youtube`
- `start datalens`
- `find files related to datalens`
- `open 1`
- `listen`
- `stop listening`
- `explain this screen`
- `remember that DataLens is my deployed project`
- `what do you remember about DataLens`
- `open chrome and search for ...`
- `turn the volume down`

## DataLens

The `start/open DataLens` command opens the deployed application directly:

`https://frontend-liard-rho-s59bfvv4uq.vercel.app`

There is no local DataLens folder launcher in this build.

## API provider variables

See `.env.example`. Recommended defaults are:

- Groq: `openai/gpt-oss-120b`
- Groq vision: `qwen/qwen3.8-27b`
- Groq STT: `whisper-large-v3-turbo`
- xKiro: `mistralai/mistral-large-2512`
- Gemini: `gemini-2.5-flash`

## Safety

Irreversible operations should use the confirmation gate. NOVA does not claim a browser action, file action, or message was successful unless the action returns a success result.

## Attribution

This distribution incorporates source code from the uploaded Mark-LV project. The original license is preserved in `LICENSE`, and attribution is retained in `THIRD_PARTY_MARK_LV_LICENSE.txt`.


## Reliable actions
- `check nova features` runs a safe local capability diagnostic.
- Explicit web/internet/network searches route to the web-search action instead of producing instructions only.
