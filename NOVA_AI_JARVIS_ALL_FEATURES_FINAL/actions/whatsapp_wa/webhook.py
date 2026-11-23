from __future__ import annotations
import json,os
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import PlainTextResponse
from .cloud_api import verify_signature,verify_webhook
from .store import connect
from .automation import handle_incoming,_log
from .reply_generator import generate_reply

app=FastAPI(title="NOVA WA Webhook",docs_url=None,redoc_url=None)

def _allowed(sender):
    allowed={x.strip().replace("+","") for x in os.getenv("NOVA_WA_ALLOWED_SENDERS","").split(",") if x.strip()}
    return "".join(ch for ch in str(sender) if ch.isdigit()) in allowed

@app.get("/webhook")
async def verify(request:Request):
    q=request.query_params
    challenge=verify_webhook(q.get("hub.mode",""),q.get("hub.verify_token",""),q.get("hub.challenge",""))
    if challenge is None: raise HTTPException(status_code=403,detail="Webhook verification failed")
    return PlainTextResponse(challenge)

@app.post("/webhook")
async def receive(request:Request):
    raw=await request.body()
    if not verify_signature(raw,request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=401,detail="Invalid webhook signature")
    try: payload=json.loads(raw.decode("utf-8"))
    except Exception: raise HTTPException(status_code=400,detail="Invalid JSON")
    handled=0
    for entry in payload.get("entry",[]):
        for change in entry.get("changes",[]):
            value=change.get("value",{})
            # Delivery/read status events are not incoming user messages.
            for msg in value.get("messages",[]):
                sender=msg.get("from",""); message_id=msg.get("id","")
                if not sender or not message_id: continue
                kind=msg.get("type","unknown")
                text=msg.get("text",{}).get("body","") if kind=="text" else f"[{kind} message]"
                allowed=_allowed(sender)
                if kind!="text":
                    with connect() as db:
                        db.execute("INSERT OR IGNORE INTO business_messages(wa_message_id,sender_wa_id,text,direction,status) VALUES(?,?,?,'inbound','needs_review')",(message_id,sender,text))
                    _log(message_id,"human_handover","Non-text message requires review.")
                    handled+=1
                    continue
                if not allowed or os.getenv("NOVA_WA_AUTOMATION_ENABLED","false").lower() not in {"1","true","yes"}:
                    with connect() as db:
                        db.execute("INSERT OR IGNORE INTO business_messages(wa_message_id,sender_wa_id,text,direction,status) VALUES(?,?,?,'inbound','received')",(message_id,sender,text))
                    _log(message_id,"human_handover","Automation disabled or sender not on allowlist.")
                    handled+=1
                    continue
                try:
                    draft=generate_reply(sender,text)
                    result=handle_incoming(sender,message_id,text,draft["reply"],draft["confidence"],allowed=True)
                    if not result.get("sent"):
                        _log(message_id,"human_handover",result.get("reason","Reply not sent"))
                except Exception as exc:
                    with connect() as db:
                        db.execute("INSERT OR IGNORE INTO business_messages(wa_message_id,sender_wa_id,text,direction,status) VALUES(?,?,?,'inbound','needs_review')",(message_id,sender,text))
                    _log(message_id,"human_handover",f"Reply generation failed: {type(exc).__name__}")
                handled+=1
    return {"received":True,"handled":handled}
