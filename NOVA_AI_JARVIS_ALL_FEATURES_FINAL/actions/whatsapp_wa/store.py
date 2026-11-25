from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "whatsapp_wa" / "nova_wa.sqlite3"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA journal_mode=WAL")
    _schema(db)
    return db

def _schema(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,source_name TEXT NOT NULL,source_type TEXT NOT NULL,imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,message_count INTEGER NOT NULL DEFAULT 0,content_sha256 TEXT NOT NULL UNIQUE);
    CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY,display_name TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY,contact_id INTEGER,import_id INTEGER NOT NULL,title TEXT NOT NULL,source_type TEXT NOT NULL DEFAULT 'personal_import',FOREIGN KEY(contact_id) REFERENCES contacts(id),FOREIGN KEY(import_id) REFERENCES imports(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,conversation_id INTEGER NOT NULL,external_id TEXT,timestamp TEXT,sender TEXT NOT NULL,text TEXT NOT NULL,message_type TEXT NOT NULL DEFAULT 'text',FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_external_id_unique ON messages(external_id) WHERE external_id IS NOT NULL AND external_id!='';
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(text,sender,content='messages',content_rowid='id');
    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN INSERT INTO messages_fts(rowid,text,sender) VALUES(new.id,new.text,new.sender); END;
    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN INSERT INTO messages_fts(messages_fts,rowid,text,sender) VALUES('delete',old.id,old.text,old.sender); END;
    CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY,content TEXT NOT NULL,kind TEXT NOT NULL,confidence REAL NOT NULL DEFAULT 0.5,confirmed INTEGER NOT NULL DEFAULT 0,source_message_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(source_message_id) REFERENCES messages(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY,title TEXT NOT NULL,due_text TEXT,status TEXT NOT NULL DEFAULT 'suggested',source_message_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(source_message_id) REFERENCES messages(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS commitments(id INTEGER PRIMARY KEY,description TEXT NOT NULL,direction TEXT NOT NULL,contact_id INTEGER,source_message_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'open',FOREIGN KEY(contact_id) REFERENCES contacts(id),FOREIGN KEY(source_message_id) REFERENCES messages(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS risk_findings(id INTEGER PRIMARY KEY,source_message_id INTEGER NOT NULL,level TEXT NOT NULL,indicators TEXT NOT NULL,explanation TEXT NOT NULL,FOREIGN KEY(source_message_id) REFERENCES messages(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS translations(id INTEGER PRIMARY KEY,source_message_id INTEGER NOT NULL,language TEXT NOT NULL,translated_text TEXT NOT NULL,FOREIGN KEY(source_message_id) REFERENCES messages(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS business_messages(id INTEGER PRIMARY KEY,wa_message_id TEXT NOT NULL UNIQUE,sender_wa_id TEXT NOT NULL,text TEXT NOT NULL,direction TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'received',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,reply_to TEXT);
    CREATE TABLE IF NOT EXISTS automation_events(id INTEGER PRIMARY KEY,wa_message_id TEXT,event_type TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    """)
def add_import(source_name: str, source_type: str, digest: str, title: str, messages: Iterable[dict]):
    rows=list(messages)
    with connect() as db:
        cur=db.execute("INSERT OR IGNORE INTO imports(source_name,source_type,content_sha256,message_count) VALUES(?,?,?,?)",(source_name,source_type,digest,len(rows)))
        if cur.rowcount==0: return {"duplicate":True,"messages":0,"import_id":None}
        import_id=cur.lastrowid
        db.execute("INSERT OR IGNORE INTO contacts(display_name) VALUES(?)",(title,))
        contact_id=db.execute("SELECT id FROM contacts WHERE display_name=?",(title,)).fetchone()[0]
        conv=db.execute("INSERT INTO conversations(contact_id,import_id,title) VALUES(?,?,?)",(contact_id,import_id,title))
        for row in rows:
            db.execute("INSERT INTO messages(conversation_id,timestamp,sender,text,message_type) VALUES(?,?,?,?,?)",(conv.lastrowid,row.get("timestamp"),row.get("sender","Unknown"),row.get("text",""),row.get("message_type","text")))
        return {"duplicate":False,"messages":len(rows),"import_id":import_id}
def search_messages(query: str, limit: int=50):
    query=(query or "").strip()
    if not query: return []
    safe='"'+query.replace('"','""')+'"'
    with connect() as db:
        try:
            rows=db.execute("SELECT m.id,m.timestamp,m.sender,m.text,c.title FROM messages_fts f JOIN messages m ON m.id=f.rowid JOIN conversations c ON c.id=m.conversation_id WHERE messages_fts MATCH ? ORDER BY m.timestamp DESC LIMIT ?",(safe,max(1,min(limit,200)))).fetchall()
        except sqlite3.OperationalError:
            rows=db.execute("SELECT m.id,m.timestamp,m.sender,m.text,c.title FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.text LIKE ? ORDER BY m.timestamp DESC LIMIT ?",(f"%{query}%",max(1,min(limit,200)))).fetchall()
        return [dict(r) for r in rows]
def overview():
    with connect() as db:
        return {"imports":db.execute("SELECT COUNT(*) FROM imports").fetchone()[0],"messages":db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],"contacts":db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],"tasks":db.execute("SELECT COUNT(*) FROM tasks WHERE status!='done'").fetchone()[0],"risks":db.execute("SELECT COUNT(*) FROM risk_findings").fetchone()[0]}


def add_waha_history(session: str, chat_id: str, title: str, messages: Iterable[dict]):
    """Upsert a limited WAHA chat history into the local message index."""
    import hashlib
    rows = list(messages)
    digest = hashlib.sha256(f"waha-history:{session}:{chat_id}".encode("utf-8")).hexdigest()
    with connect() as db:
        cur = db.execute(
            "INSERT OR IGNORE INTO imports(source_name,source_type,content_sha256,message_count) VALUES(?,?,?,?)",
            (f"WAHA history {chat_id}", "waha_sync", digest, len(rows)),
        )
        if cur.rowcount:
            import_id = cur.lastrowid
        else:
            import_id = db.execute("SELECT id FROM imports WHERE content_sha256=?", (digest,)).fetchone()[0]
        conv = db.execute("SELECT id FROM conversations WHERE import_id=? LIMIT 1", (import_id,)).fetchone()
        if conv:
            conversation_id = conv[0]
        else:
            db.execute("INSERT OR IGNORE INTO contacts(display_name) VALUES(?)", (title,))
            contact_id = db.execute("SELECT id FROM contacts WHERE display_name=?", (title,)).fetchone()[0]
            conversation_id = db.execute(
                "INSERT INTO conversations(contact_id,import_id,title,source_type) VALUES(?,?,?,'waha_sync')",
                (contact_id, import_id, title),
            ).lastrowid
        added = 0
        for row in rows:
            external_id = str(row.get("id") or "").strip()
            text = str(row.get("body") or row.get("text") or "").strip()
            if not text:
                continue
            if not external_id:
                external_id = hashlib.sha256(f"{chat_id}|{row.get('timestamp')}|{text}".encode("utf-8")).hexdigest()
            timestamp = row.get("timestamp")
            if isinstance(timestamp, (int, float)):
                from datetime import datetime, timezone
                timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat()
            sender = "Me" if row.get("fromMe") else str(row.get("participant") or row.get("from") or title)
            cur = db.execute(
                "INSERT OR IGNORE INTO messages(conversation_id,external_id,timestamp,sender,text,message_type) VALUES(?,?,?,?,?,'text')",
                (conversation_id, external_id, str(timestamp or ""), sender, text),
            )
            added += max(cur.rowcount, 0)
        db.execute("UPDATE imports SET message_count=(SELECT COUNT(*) FROM messages WHERE conversation_id=?) WHERE id=?", (conversation_id, import_id))
        return {"added": added, "total": len(rows), "conversation_id": conversation_id}
