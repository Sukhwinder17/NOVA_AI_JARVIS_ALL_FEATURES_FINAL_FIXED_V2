from __future__ import annotations
import os,re
from . import cloud_api
from .store import connect
_BLOCKED=re.compile(r"\b(?:otp|one[- ]time password|password|pin|bank account|credit card|debit card)\b",re.I)
_PAYMENT=re.compile(r"\b(?:transfer|send|pay)\b.{0,50}\b(?:money|cash|upi|bank|fee|deposit)\b",re.I)
def _log(message_id,event_type,detail):
 with connect() as db: db.execute("INSERT INTO automation_events(wa_message_id,event_type,detail) VALUES(?,?,?)",(message_id,event_type,detail[:500]))
def should_auto_reply(text,confidence,allowed=False):
 if os.getenv("NOVA_WA_AUTOMATION_ENABLED","false").lower() not in {"1","true","yes"}: return False,"Automation is disabled."
 if not allowed: return False,"Sender is not allowlisted."
 if confidence<float(os.getenv("NOVA_WA_MIN_CONFIDENCE","0.82")): return False,"Confidence below threshold."
 if _BLOCKED.search(text or "") or _PAYMENT.search(text or ""): return False,"Sensitive or financial topic requires human review."
 return True,"Eligible for automatic reply."
def handle_incoming(sender,message_id,text,reply_text,confidence=0.0,allowed=False):
 if not message_id or not sender or not text: return {"sent":False,"reason":"Incomplete incoming message."}
 with connect() as db:
  cur=db.execute("INSERT OR IGNORE INTO business_messages(wa_message_id,sender_wa_id,text,direction,status) VALUES(?,?,?,'inbound','received')",(message_id,sender,text))
  if cur.rowcount==0: return {"sent":False,"reason":"Duplicate webhook event."}
 ok,reason=should_auto_reply(text,confidence,allowed)
 if not ok: _log(message_id,"human_handover",reason); return {"sent":False,"reason":reason}
 result=cloud_api.send_text(sender,reply_text)
 sent_id=result.get("messages",[{}])[0].get("id","out-"+message_id)
 with connect() as db: db.execute("INSERT OR IGNORE INTO business_messages(wa_message_id,sender_wa_id,text,direction,status,reply_to) VALUES(?,?,?,'outbound','submitted',?)",(sent_id,sender,reply_text,message_id))
 _log(message_id,"auto_reply_submitted","Reply submitted to WhatsApp Cloud API.")
 return {"sent":True,"reason":"Submitted to WhatsApp Cloud API.","response":result}
