from __future__ import annotations
import hashlib,re
from pathlib import Path
from datetime import datetime
from .store import add_import

_PATTERNS=[
 re.compile(r"^\[(?P<date>[^]]+)\] (?P<sender>[^:]+): (?P<text>.*)$"),
 re.compile(r"^(?P<date>\d{1,2}/\d{1,2}/\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?(?:\s?[APap][Mm])?) - (?P<sender>[^:]+): (?P<text>.*)$")
]
def _timestamp(value):
 value=value.strip()
 for fmt in ("%d/%m/%y, %H:%M:%S","%d/%m/%y, %H:%M","%d/%m/%Y, %H:%M:%S","%d/%m/%Y, %H:%M","%m/%d/%y, %I:%M %p","%m/%d/%Y, %I:%M %p"):
  try: return datetime.strptime(value,fmt).isoformat()
  except ValueError: pass
 return value
def parse_export(text):
 messages,current=[],None
 for line in text.replace("\ufeff","").splitlines():
  match=next((m for p in _PATTERNS if (m:=p.match(line))),None)
  if match:
   if current: messages.append(current)
   current={"timestamp":_timestamp(match.group("date")),"sender":match.group("sender").strip(),"text":match.group("text")}
  elif current is not None: current["text"]+="\n"+line
 if current: messages.append(current)
 return messages
def import_txt(path,conversation_name=None):
 file=Path(path)
 if not file.is_file() or file.suffix.lower()!=".txt": raise ValueError("Choose a valid WhatsApp exported .txt file.")
 if file.stat().st_size>25*1024*1024: raise ValueError("Chat export exceeds the 25 MB import limit.")
 raw=file.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
 messages=parse_export(raw.decode("utf-8-sig",errors="replace"))
 if not messages: raise ValueError("No supported WhatsApp export format detected; nothing was imported.")
 title=(conversation_name or file.stem).strip()[:120]
 return {**add_import(file.name,"whatsapp_txt",digest,title,messages),"title":title}
def import_text(text,conversation_name="Pasted conversation"):
 raw=(text or "").strip()
 if not raw: raise ValueError("Paste at least one message.")
 digest=hashlib.sha256(raw.encode("utf-8")).hexdigest(); messages=parse_export(raw)
 if not messages: messages=[{"timestamp":datetime.now().astimezone().isoformat(),"sender":"Imported selection","text":raw}]
 return {**add_import("pasted_messages.txt","selected_text",digest,conversation_name[:120],messages),"title":conversation_name}
