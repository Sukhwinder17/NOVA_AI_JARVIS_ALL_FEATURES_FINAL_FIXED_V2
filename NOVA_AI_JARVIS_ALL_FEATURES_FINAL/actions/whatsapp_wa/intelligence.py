from __future__ import annotations
import re
from .store import connect
_RISK=[
 ("critical",re.compile(r"\b(?:otp|one[- ]time password|verification code|password|pin)\b",re.I),"Requests or mentions authentication secrets."),
 ("high",re.compile(r"\b(?:send|transfer|pay)\b.{0,50}\b(?:money|cash|upi|bank|fee|deposit)\b",re.I),"Contains a payment request."),
 ("high",re.compile(r"https?://[^\s]+",re.I),"Contains a link; verify its destination independently."),
 ("medium",re.compile(r"\b(?:urgent|immediately|account blocked|act now|limited time)\b",re.I),"Uses urgency or pressure language.")]
_TASK=re.compile(r"\b(?:please|kindly|need you to|can you|don't forget to|remember to)\s+(.{5,180})",re.I)
_PROMISE=re.compile(r"\b(?:i will|i'll|i shall|i promise|will send|will share|will call)\b",re.I)
def analyse_imported_messages(limit=5000):
 result={"risks":0,"tasks":0,"commitments":0}
 with connect() as db:
  rows=db.execute("SELECT id,text FROM messages ORDER BY id DESC LIMIT ?",(max(1,min(limit,20000)),)).fetchall()
  for row in rows:
   text=row["text"] or ""
   for level,pattern,explanation in _RISK:
    if pattern.search(text):
     key=pattern.pattern
     db.execute("INSERT INTO risk_findings(source_message_id,level,indicators,explanation) SELECT ?,?,?,? WHERE NOT EXISTS(SELECT 1 FROM risk_findings WHERE source_message_id=? AND indicators=?)",(row["id"],level,key,explanation,row["id"],key)); result["risks"]+=1
   task=_TASK.search(text)
   if task:
    title=task.group(1).strip()
    db.execute("INSERT INTO tasks(title,source_message_id) SELECT ?,? WHERE NOT EXISTS(SELECT 1 FROM tasks WHERE source_message_id=? AND title=?)",(title,row["id"],row["id"],title)); result["tasks"]+=1
   if _PROMISE.search(text):
    db.execute("INSERT INTO commitments(description,direction,source_message_id) SELECT ?,'outgoing',? WHERE NOT EXISTS(SELECT 1 FROM commitments WHERE source_message_id=?)",(text[:240],row["id"],row["id"])); result["commitments"]+=1
 return result
def create_memory(content,source_message_id,kind="note"):
 content=(content or "").strip()
 if not content or len(content)>2000: raise ValueError("Memory must contain 1–2000 characters.")
 with connect() as db:
  if not db.execute("SELECT 1 FROM messages WHERE id=?",(source_message_id,)).fetchone(): raise ValueError("Source message does not exist.")
  db.execute("INSERT INTO memories(content,kind,confidence,source_message_id) VALUES(?,?,0.8,?)",(content,kind[:40],source_message_id))
def approve_task(task_id):
 with connect() as db: return db.execute("UPDATE tasks SET status='approved' WHERE id=? AND status='suggested'",(int(task_id),)).rowcount==1
