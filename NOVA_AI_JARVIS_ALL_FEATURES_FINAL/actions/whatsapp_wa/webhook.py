from __future__ import annotations
import json
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import PlainTextResponse
from .cloud_api import verify_signature,verify_webhook
from .store import connect
app=FastAPI(title="NOVA WA Webhook",docs_url=None,redoc_url=None)
@app.get("/webhook")
async def verify(request:Request):
 q=request.query_params
 challenge=verify_webhook(q.get("hub.mode",""),q.get("hub.verify_token",""),q.get("hub.challenge",""))
 if challenge is None: raise HTTPException(status_code=403,detail="Webhook verification failed")
 return PlainTextResponse(challenge)
@app.post("/webhook")
async def receive(request:Request):
 raw=await request.body()
 if not verify_signature(raw,request.headers.get("X-Hub-Signature-256")): raise HTTPException(status_code=401,detail="Invalid webhook signature")
 try: payload=json.loads(raw.decode("utf-8"))
 except Exception: raise HTTPException(status_code=400,detail="Invalid JSON")
 with connect() as db:
  for entry in payload.get("entry",[]):
   for change in entry.get("changes",[]):
    for msg in change.get("value",{}).get("messages",[]):
     text=msg.get("text",{}).get("body","") if msg.get("type")=="text" else f"[{msg.get('type','unknown')} message]"
     db.execute("INSERT OR IGNORE INTO business_messages(wa_message_id,sender_wa_id,text,direction,status) VALUES(?,?,?,'inbound','received')",(msg.get("id",""),msg.get("from",""),text))
 return {"received":True}
