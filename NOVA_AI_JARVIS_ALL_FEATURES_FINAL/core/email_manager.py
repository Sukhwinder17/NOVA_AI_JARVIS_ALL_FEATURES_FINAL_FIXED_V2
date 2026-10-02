from __future__ import annotations
import email, imaplib, json, re, ssl, os, webbrowser
from email.header import decode_header
from pathlib import Path
from typing import Any
from . import config

STORE = config.BASE_DIR / "data" / "email_accounts.json"


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]
GMAIL_TOKEN_DIR = config.BASE_DIR / "data" / "gmail_tokens_v2"
GMAIL_SETUP_URL = "https://console.cloud.google.com/auth/clients"
GMAIL_CREDENTIAL_ENV = "NOVA_GOOGLE_CREDENTIALS"

def _gmail_credentials_file() -> Path | None:
    """Find the local Desktop OAuth client JSON without ever storing it in the repo."""
    configured = os.getenv(GMAIL_CREDENTIAL_ENV, "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        config.BASE_DIR / "config" / "google_credentials.json",
        config.BASE_DIR / "config" / "credentials.json",
        config.BASE_DIR / "credentials.json",
    ])
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None

def _gmail_setup_message() -> str:
    """Open Google's official client page and return a one-time setup message."""
    try:
        webbrowser.open(GMAIL_SETUP_URL)
    except Exception:
        pass
    return (
        "Gmail needs a one-time Google Desktop OAuth setup. "
        "I opened Google's OAuth Clients page. Create a Desktop app OAuth client, "
        "download its JSON, and save it as "
        f"{config.BASE_DIR / 'config' / 'google_credentials.json'}. "
        "Then run 'connect email' again. Your Gmail password is never entered into NOVA."
    )

def _safe_token_name(address: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", address or "gmail")

def _delete_bad_token(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

def connect_gmail_oauth(email_hint: str = "") -> str:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Gmail OAuth packages are missing. Run: "
            "pip install -r requirements.txt"
        )

    cred_file = _gmail_credentials_file()
    if not cred_file:
        return _gmail_setup_message()

    GMAIL_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    hint = email_hint.strip().lower()
    token_file = GMAIL_TOKEN_DIR / f"{_safe_token_name(hint or 'gmail')}.json"
    creds = None

    if token_file.exists():
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)
        except Exception:
            _delete_bad_token(token_file)
            creds = None

    if creds and creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        except Exception:
            _delete_bad_token(token_file)
            creds = None

    # Reuse a valid token only if it belongs to the requested Gmail account.
    if creds and creds.valid:
        try:
            from googleapiclient.discovery import build
            service = build("gmail", "v1", credentials=creds, cache_discovery=False)
            profile = service.users().getProfile(userId="me").execute()
            actual = (profile.get("emailAddress") or "").strip().lower()
            if hint and actual and actual != hint:
                _delete_bad_token(token_file)
                creds = None
        except Exception:
            _delete_bad_token(token_file)
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), GMAIL_SCOPES)
        # login_hint preselects the address when Google supports it; the password
        # remains entirely inside Google's browser page.
        # Always show Google's account chooser on a fresh sign-in.
        # The user never types their Gmail password into NOVA.
        kwargs = {"open_browser": True, "prompt": "select_account"}
        if hint:
            kwargs["login_hint"] = hint
        creds = flow.run_local_server(
            host="127.0.0.1",
            bind_addr="127.0.0.1",
            port=0,
            **kwargs,
        )
        token_file.write_text(creds.to_json(), encoding="utf-8")

    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    address = (profile.get("emailAddress") or email_hint).strip()
    if not address:
        raise RuntimeError("Google sign-in completed but Gmail did not return the account address.")

    # Keep one stable token per actual Google account.
    actual_token = GMAIL_TOKEN_DIR / f"{_safe_token_name(address)}.json"
    if actual_token != token_file:
        actual_token.write_text(creds.to_json(), encoding="utf-8")
        _delete_bad_token(token_file)
        token_file = actual_token

    data = _load()
    data[address.lower()] = {
        "email": address,
        "type": "gmail_oauth",
        "token": str(token_file),
    }
    _save(data)
    return f"Connected to {address} with Google OAuth. No email password was stored."

def _gmail_service(address: str):
    item = _load().get(address.lower().strip())
    if not item or item.get("type") != "gmail_oauth": return None
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request

    token_path = Path(item["token"])
    if not token_path.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        if not creds.valid:
            return None
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception:
        return None

def _gmail_headers(msg):
    headers = msg.get("payload", {}).get("headers", [])
    def geth(name):
        return next((h.get("value", "") for h in headers if h.get("name", "").lower() == name.lower()), "")
    return {"subject": geth("Subject"), "from": geth("From"), "to": geth("To"), "cc": geth("Cc"), "date": geth("Date"), "message_id": geth("Message-ID")}

def _gmail_message(service, message_id: str):
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()

def gmail_search(address: str, query: str, limit: int = 20) -> list[dict]:
    service = _gmail_service(address)
    if not service: raise RuntimeError("Gmail OAuth is not connected. Use 'connect email' first.")
    result = service.users().messages().list(userId="me", q=query, maxResults=max(1, min(limit, 100))).execute()
    rows=[]
    for item in result.get("messages", []):
        msg=_gmail_message(service,item["id"]); h=_gmail_headers(msg)
        rows.append({"id":item["id"],"thread_id":item.get("threadId",""),"subject":h["subject"] or "(no subject)","from":h["from"],"to":h["to"],"date":h["date"],"snippet":msg.get("snippet",""),"labels":msg.get("labelIds",[]),"body":_gmail_text(msg.get("payload",{}))})
    return rows

def gmail_send(address: str, to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
    import base64
    from email.message import EmailMessage
    service=_gmail_service(address)
    if not service: raise RuntimeError("Gmail OAuth is not connected. Use 'connect email' first.")
    msg=EmailMessage(); msg["To"]=to; msg["Subject"]=subject
    if cc: msg["Cc"]=cc
    if bcc: msg["Bcc"]=bcc
    msg.set_content(body)
    raw=base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    sent=service.users().messages().send(userId="me",body={"raw":raw}).execute()
    return sent.get("id","")

def gmail_modify(address: str, message_id: str, add_labels=None, remove_labels=None) -> None:
    service=_gmail_service(address)
    if not service: raise RuntimeError("Gmail OAuth is not connected. Use 'connect email' first.")
    service.users().messages().modify(userId="me",id=message_id,body={"addLabelIds":add_labels or [],"removeLabelIds":remove_labels or []}).execute()

def gmail_trash(address: str, message_id: str) -> None:
    service=_gmail_service(address)
    if not service: raise RuntimeError("Gmail OAuth is not connected. Use 'connect email' first.")
    service.users().messages().trash(userId="me",id=message_id).execute()

def gmail_reply(address: str, message_id: str, body: str) -> str:
    import base64
    from email.message import EmailMessage
    service=_gmail_service(address)
    if not service: raise RuntimeError("Gmail OAuth is not connected. Use 'connect email' first.")
    original=_gmail_message(service,message_id); h=_gmail_headers(original)
    subject=h["subject"] or ""
    if not subject.lower().startswith("re:"): subject="Re: "+subject
    msg=EmailMessage(); msg["To"]=h["from"]; msg["Subject"]=subject
    if h["message_id"]: msg["In-Reply-To"]=h["message_id"]; msg["References"]=h["message_id"]
    msg.set_content(body)
    raw=base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    sent=service.users().messages().send(userId="me",body={"raw":raw,"threadId":original.get("threadId","")}).execute()
    return sent.get("id","")

def _gmail_text(payload):
    import base64
    out=[]
    def walk(part):
        if part.get("mimeType")=="text/plain" and part.get("body",{}).get("data"):
            try: out.append(base64.urlsafe_b64decode(part["body"]["data"]+"==").decode("utf-8",errors="replace"))
            except Exception: pass
        for child in part.get("parts",[]) or []: walk(child)
    walk(payload)
    return "
".join(out)

PROVIDERS = {
    "gmail.com": ("imap.gmail.com", 993),
    "googlemail.com": ("imap.gmail.com", 993),
    "outlook.com": ("outlook.office365.com", 993),
    "hotmail.com": ("outlook.office365.com", 993),
    "live.com": ("outlook.office365.com", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
    "icloud.com": ("imap.mail.me.com", 993),
}

def _decode(v: str) -> str:
    out=[]
    for part, enc in decode_header(v or ""):
        out.append(part.decode(enc or "utf-8", errors="replace") if isinstance(part, bytes) else str(part))
    return "".join(out)

def _load() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save(data: dict) -> None:
    """Persist email account metadata/tokens without ever exposing passwords in logs."""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def save_account(address: str, password: str, host: str = "", port: int = 993) -> None:
    """Validate IMAP credentials first, then persist them.

    Gmail App Passwords are often copied with spaces; Gmail IMAP needs the
    actual 16-character value without those spaces. A normal Google account
    password is not accepted by Gmail's third-party password IMAP flow.
    """
    address = address.strip()
    domain = address.rsplit("@", 1)[-1].lower()
    default_host, default_port = PROVIDERS.get(domain, ("", 993))
    host = (host or default_host).strip()
    if not host:
        raise ValueError("Unknown provider. Provide its IMAP server.")

    raw_password = str(password or "")
    if domain in ("gmail.com", "googlemail.com"):
        password = re.sub(r"\s+", "", raw_password)
    else:
        password = raw_password
    if not password:
        raise ValueError("Password cannot be empty.")

    # Validate BEFORE writing anything to disk.
    box = None
    try:
        box = imaplib.IMAP4_SSL(
            host,
            int(port or default_port),
            ssl_context=ssl.create_default_context(),
        )
        box.login(address, password)
    except imaplib.IMAP4.error as exc:
        if domain in ("gmail.com", "googlemail.com"):
            raise RuntimeError(
                "Gmail rejected these credentials. If you entered your normal "
                "Gmail password, use a Google App Password (16 characters) "
                "instead. App Passwords require 2-Step Verification."
            ) from exc
        raise RuntimeError(f"Email server rejected the credentials: {exc}") from exc
    finally:
        if box is not None:
            try:
                box.logout()
            except Exception:
                pass

    data = _load()
    data[address.lower()] = {
        "email": address,
        "password": password,
        "host": host,
        "port": int(port or default_port),
        "type": "imap_password",
    }
    _save(data)

def accounts() -> list[str]: return list(_load().keys())

def _connect(address: str):
    item=_load().get(address.lower().strip())
    if not item: raise ValueError(f"Email account '{address}' is not connected.")
    box=imaplib.IMAP4_SSL(item["host"], int(item.get("port",993)), ssl_context=ssl.create_default_context())
    box.login(item["email"], item["password"])
    return box

def _body(msg) -> str:
    parts=[]
    for p in msg.walk() if msg.is_multipart() else [msg]:
        if p.get_content_type()=="text/plain" and not p.get_filename():
            try: parts.append(p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace"))
            except Exception: pass
    return "
".join(parts)

def _classify(subject, body, sender):
    t=f"{subject} {body} {sender}".lower()
    if any(x in t for x in ("unsubscribe","sale","offer","discount","promotion","deal","newsletter")): return "PROMOTION"
    if any(x in t for x in ("urgent","action required","due today","due tomorrow","deadline")): return "URGENT"
    if any(x in t for x in ("assignment","homework","submission","practical","project","lab report")): return "ASSIGNMENT"
    if any(x in t for x in ("meeting","client","office","work","task","interview")): return "WORK"
    return "OTHER"

def _deadline(text):
    patterns=[
        r"\b(?:due|deadline|submit(?:ted| by)?|submission)\b.{0,90}\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\b(?:due|deadline|submit(?:ted| by)?|submission)\b.{0,100}\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b",
        r"\b(?:due|deadline|submit(?:ted| by)?|submission)\b.{0,100}\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    ]
    for p in patterns:
        m=re.search(p,text,re.I|re.S)
        if m: return re.sub(r"\s+"," ",m.group(0)).strip()
    return ""

def inbox(address: str, limit: int=25) -> list[dict[str,Any]]:
    gmail=_gmail_service(address)
    domain = address.rsplit("@", 1)[-1].lower().strip() if "@" in address else ""
    # Never fall back to legacy password IMAP for Gmail. That old path is what
    # produced AUTHENTICATIONFAILED and defeats the passwordless OAuth design.
    if domain in ("gmail.com", "googlemail.com") and gmail is None:
        item = _load().get(address.lower().strip(), {})
        if item.get("type") != "imap_password":
            raise RuntimeError(
                "Gmail is not connected with Google OAuth yet. "
                "Use 'connect email' and finish the Google sign-in, "
                "or reconnect using a Google App Password."
            )
    if gmail:
        result=gmail.users().messages().list(userId="me",labelIds=["INBOX"],maxResults=limit).execute()
        rows=[]
        for item in result.get("messages",[]):
            msg=gmail.users().messages().get(userId="me",id=item["id"],format="full").execute()
            headers=msg.get("payload",{}).get("headers",[])
            def geth(n): return next((h.get("value","") for h in headers if h.get("name","").lower()==n.lower()),"")
            subject,sender=geth("Subject"),geth("From")
            body=_gmail_text(msg.get("payload",{}))
            rows.append({"subject":subject or "(no subject)","from":sender,"date":geth("Date"),
                         "category":_classify(subject,body,sender),"deadline":_deadline(subject+"
"+body),
                         "attachments":[p.get("filename") for p in msg.get("payload",{}).get("parts",[]) if p.get("filename")],
                         "snippet":msg.get("snippet","")})
        return rows
    box=_connect(address)
    try:
        status,_=box.select("INBOX",readonly=True)
        if status!="OK": return []
        _,data=box.search(None,"ALL")
        ids=data[0].split()[-limit:]
        rows=[]
        for mid in reversed(ids):
            status,raw=box.fetch(mid,"(RFC822)")
            if status!="OK" or not raw or not raw[0]: continue
            msg=email.message_from_bytes(raw[0][1])
            subject=_decode(msg.get("Subject","")); sender=_decode(msg.get("From","")); body=""
            for p in msg.walk() if msg.is_multipart() else [msg]:
                if p.get_content_type()=="text/plain" and not p.get_filename():
                    try: body+=p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8",errors="replace")
                    except Exception: pass
            rows.append({"subject":subject or "(no subject)","from":sender,"date":msg.get("Date",""),
                         "category":_classify(subject,body,sender),"deadline":_deadline(subject+"
"+body),
                         "attachments":[p.get_filename() for p in msg.walk() if p.get_filename()] if msg.is_multipart() else [],
                         "snippet":re.sub(r"\s+"," ",body).strip()[:220]})
        return rows
    finally:
        try: box.logout()
        except Exception: pass

def summarize(address: str, limit=25) -> str:
    rows=inbox(address,limit)
    if not rows: return "No emails found."
    groups={k:[] for k in ("URGENT","ASSIGNMENT","WORK","PROMOTION","OTHER")}
    for r in rows: groups[r["category"]].append(r)
    titles={"URGENT":"🔴 URGENT / DEADLINES","ASSIGNMENT":"📚 ASSIGNMENTS / STUDY","WORK":"💼 WORK / TASKS","PROMOTION":"🛍️ PROMOTIONS","OTHER":"📨 OTHER"}
    lines=[f"📧 EMAIL BRIEF — {address}",""]
    for k in titles:
        if groups[k]:
            lines.append(titles[k])
            for r in groups[k]:
                dl=f" — {r['deadline']}" if r["deadline"] else ""
                lines.append(f"• {r['subject']} — {r['from']}{dl}")
            lines.append("")
    return "
".join(lines).strip()
