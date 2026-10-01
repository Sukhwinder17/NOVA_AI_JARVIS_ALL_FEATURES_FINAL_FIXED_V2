from __future__ import annotations
import email, imaplib, json, re, ssl
from email.header import decode_header
from pathlib import Path
from typing import Any
from . import config

STORE = config.BASE_DIR / "data" / "email_accounts.json"


GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GMAIL_TOKEN_DIR = config.BASE_DIR / "data" / "gmail_tokens"

def connect_gmail_oauth(email_hint: str = "") -> str:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("Install Gmail OAuth packages: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2")
    candidates = [config.BASE_DIR / "config" / "google_credentials.json", config.BASE_DIR / "credentials.json"]
    cred_file = next((p for p in candidates if p.exists()), None)
    if not cred_file:
        raise FileNotFoundError("Put Google Desktop OAuth credentials at config\\google_credentials.json. Google will handle sign-in; NOVA does not need your Gmail password.")
    GMAIL_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", email_hint or "gmail")
    token_file = GMAIL_TOKEN_DIR / f"{safe}.json"
    creds = None
    if token_file.exists():
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile = service.users().getProfile(userId="me").execute()
    address = profile.get("emailAddress") or email_hint
    data = _load()
    data[address.lower()] = {"email": address, "type": "gmail_oauth", "token": str(token_file)}
    _save(data)
    return f"Connected to {address} with Google OAuth. No email password was stored."

def _gmail_service(address: str):
    item = _load().get(address.lower().strip())
    if not item or item.get("type") != "gmail_oauth": return None
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(item["token"], GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        Path(item["token"]).write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

def _gmail_text(payload):
    import base64
    out=[]
    def walk(part):
        if part.get("mimeType")=="text/plain" and part.get("body",{}).get("data"):
            try: out.append(base64.urlsafe_b64decode(part["body"]["data"]+"==").decode("utf-8",errors="replace"))
            except Exception: pass
        for child in part.get("parts",[]) or []: walk(child)
    walk(payload)
    return "\n".join(out)

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
    try: return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception: return {}

def save_account(address: str, password: str, host: str = "", port: int = 993) -> None:
    address=address.strip()
    domain=address.rsplit("@",1)[-1].lower()
    default_host, default_port=PROVIDERS.get(domain, ("", 993))
    host=(host or default_host).strip()
    if not host: raise ValueError("Unknown provider. Provide its IMAP server.")
    data=_load()
    data[address.lower()]={"email":address,"password":password,"host":host,"port":int(port or default_port)}
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data), encoding="utf-8")

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
    return "\n".join(parts)

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
                         "category":_classify(subject,body,sender),"deadline":_deadline(subject+"\n"+body),
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
                         "category":_classify(subject,body,sender),"deadline":_deadline(subject+"\n"+body),
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
    return "\n".join(lines).strip()
