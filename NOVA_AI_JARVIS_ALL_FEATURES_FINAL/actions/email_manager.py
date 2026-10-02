from __future__ import annotations
from core.email_manager import accounts, inbox, save_account, summarize, connect_gmail_oauth, gmail_search, gmail_send, gmail_reply, gmail_modify, gmail_trash, _load, _save

def email_manager(parameters: dict, player=None, **kwargs) -> str:
    p=parameters or {}; action=str(p.get("action","summary")).lower().strip()
    account=str(p.get("account","")).strip()
    if action=="connect":
        address=str(p.get("email",account)).strip()
        # No email input is required for Gmail: Google will show its own
        # account chooser/sign-in page and return the actual account address.
        if not address:
            try:
                return connect_gmail_oauth("")
            except Exception as exc:
                return f"Could not start Google sign-in: {exc}"
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
        if action=="search":
            query=str(p.get("query","")).strip()
            if not query: return "Provide a Gmail search query."
            rows=gmail_search(account, query, int(p.get("limit",25) or 25))
            return "\n".join([f"📧 SEARCH RESULTS — {account}"]+[f"• {r['subject']} — {r['from']} — {r['date']}" for r in rows]) if rows else "No matching emails found."
        if action=="send":
            to=str(p.get("to","")).strip(); subject=str(p.get("subject","")).strip(); body=str(p.get("body",""))
            if not to or not subject or not body: return "Send requires to, subject, and body."
            gmail_send(account,to,subject,body,str(p.get("cc","")),str(p.get("bcc","")))
            return f"Email sent to {to}."
        if action=="reply":
            message_id=str(p.get("message_id","")).strip(); body=str(p.get("body",""))
            if not message_id or not body: return "Reply requires message_id and body."
            gmail_reply(account,message_id,body); return "Reply sent."
        if action=="trash":
            message_id=str(p.get("message_id","")).strip()
            if not message_id: return "Trash requires message_id."
            gmail_trash(account,message_id); return "Email moved to trash."
        if action=="read":
            message_id=str(p.get("message_id","")).strip()
            if not message_id: return "Read requires message_id."
            rows=gmail_search(account,f"rfc822msgid:{message_id}",1)
            return rows[0].get("body","") if rows else "Email not found."
        rows=inbox(account, int(p.get("limit",25) or 25))
        if action in ("summary","check","inbox"):
            return summarize(account,int(p.get("limit",25) or 25))
        if action=="important":
            hits=[r for r in rows if r["category"] in ("URGENT","ASSIGNMENT","WORK")]
            return "\n".join(["🔎 IMPORTANT EMAILS"]+[f"• [{r['category']}] {r['subject']} — {r['from']}" for r in hits]) if hits else "No urgent, assignment, or work emails found."
        if action=="deadlines":
            hits=[r for r in rows if r["deadline"]]
            return "\n".join(["📅 EMAIL DEADLINES"]+[f"• {r['subject']} — {r['deadline']} — {r['from']}" for r in hits]) if hits else "No explicit deadlines found in the latest emails."
        return "Email actions: connect, accounts, summary, important, deadlines, search, read, send, reply, trash."
    except Exception as exc: return f"Email check failed: {exc}"

TOOL={"name":"email_manager","description":"Manage Gmail with Google OAuth or other email accounts via IMAP; summarize, search, read, send, reply, and organize messages.","parameters":{"type":"OBJECT","properties":{"action":{"type":"STRING"},"email":{"type":"STRING"},"password":{"type":"STRING"},"account":{"type":"STRING"},"imap_host":{"type":"STRING"},"query":{"type":"STRING"},"to":{"type":"STRING"},"subject":{"type":"STRING"},"body":{"type":"STRING"},"cc":{"type":"STRING"},"bcc":{"type":"STRING"},"message_id":{"type":"STRING"},"limit":{"type":"INTEGER"}},"required":["action"]},"handler":email_manager}
