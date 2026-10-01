from __future__ import annotations
from core.email_manager import accounts, inbox, save_account, summarize, connect_gmail_oauth, _load, _save

def email_manager(parameters: dict, player=None, **kwargs) -> str:
    p=parameters or {}; action=str(p.get("action","summary")).lower().strip()
    account=str(p.get("account","")).strip()
    if action=="connect":
        address=str(p.get("email",account)).strip()
        if not address: return "Tell me the email address to connect."
        try:
            password = str(p.get("password", "") or "")
            # If the UI supplies a password, explicitly use password/IMAP mode.
            # This is useful for providers that support IMAP passwords and for
            # Gmail accounts using a Google App Password.
            if password:
                host = str(p.get("imap_host", "")).strip()
                save_account(address, password, host)
                item = _load()
                item[address.lower()]["type"] = "imap_password"
                _save(item)
                inbox(address, 1)  # validate BEFORE reporting success
                return f"Connected to {address}."
            if address.lower().endswith(("@gmail.com","@googlemail.com")):
                return connect_gmail_oauth(address)
            return "Enter your email password to connect. For Gmail, use a Google App Password if normal password login is rejected."
        except Exception as exc:
            return f"Could not connect {address}: {exc}"

    if action=="accounts":
        xs=accounts(); return "Connected email accounts:\n"+("\n".join("• "+x for x in xs) if xs else "No accounts connected.")
    if not account:
        xs=accounts()
        if not xs: return "No email account is connected. Use 'connect email' first."
        account=xs[0]
    try:
        rows=inbox(account, int(p.get("limit",25) or 25))
        if action in ("summary","check","inbox"):
            return summarize(account,int(p.get("limit",25) or 25))
        if action=="important":
            hits=[r for r in rows if r["category"] in ("URGENT","ASSIGNMENT","WORK")]
            return "\n".join(["🔎 IMPORTANT EMAILS"]+[f"• [{r['category']}] {r['subject']} — {r['from']}" for r in hits]) if hits else "No urgent, assignment, or work emails found."
        if action=="deadlines":
            hits=[r for r in rows if r["deadline"]]
            return "\n".join(["📅 EMAIL DEADLINES"]+[f"• {r['subject']} — {r['deadline']} — {r['from']}" for r in hits]) if hits else "No explicit deadlines found in the latest emails."
        return "Email actions: connect, accounts, summary, important, deadlines."
    except Exception as exc: return f"Email check failed: {exc}"

TOOL={"name":"email_manager","description":"Analyze connected email inboxes via IMAP; classify urgent, assignments, work, promotions and other messages and extract explicit deadlines.","parameters":{"type":"OBJECT","properties":{"action":{"type":"STRING"},"email":{"type":"STRING"},"password":{"type":"STRING"},"account":{"type":"STRING"},"imap_host":{"type":"STRING"},"limit":{"type":"INTEGER"}},"required":["action"]},"handler":email_manager}
