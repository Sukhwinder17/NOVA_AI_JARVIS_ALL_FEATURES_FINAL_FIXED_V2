from __future__ import annotations
import hashlib,hmac,os,requests
GRAPH_VERSION=os.getenv("NOVA_WA_GRAPH_VERSION","v27.0")
BASE_URL=f"https://graph.facebook.com/{GRAPH_VERSION}"
def _credentials():
 token=os.getenv("NOVA_WA_ACCESS_TOKEN","").strip(); phone_id=os.getenv("NOVA_WA_PHONE_NUMBER_ID","").strip()
 if not token or not phone_id: raise RuntimeError("WhatsApp Business Cloud API is not configured; set credentials in local .env.")
 return token,phone_id
def verify_signature(raw_body,signature_header):
 secret=os.getenv("NOVA_WA_APP_SECRET","").strip()
 if not secret or not signature_header or not signature_header.startswith("sha256="): return False
 expected="sha256="+hmac.new(secret.encode(),raw_body,hashlib.sha256).hexdigest()
 return hmac.compare_digest(expected,signature_header)
def send_text(to,body):
 token,phone_id=_credentials(); recipient="".join(c for c in str(to) if c.isdigit()); body=str(body or "").strip()
 if not 7<=len(recipient)<=15 or not body or len(body)>4096: raise ValueError("Provide a valid international number and a message of 1–4096 characters.")
 response=requests.post(f"{BASE_URL}/{phone_id}/messages",headers={"Authorization":f"Bearer {token}"},json={"messaging_product":"whatsapp","recipient_type":"individual","to":recipient,"type":"text","text":{"preview_url":False,"body":body}},timeout=20)
 if not response.ok: raise RuntimeError(f"WhatsApp Cloud API returned HTTP {response.status_code}.")
 return response.json()
def verify_webhook(mode,token,challenge):
 expected=os.getenv("NOVA_WA_VERIFY_TOKEN","").strip()
 return challenge if mode=="subscribe" and expected and hmac.compare_digest(token or "",expected) else None
