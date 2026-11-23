from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTabWidget,
    QWidget,QFileDialog,QPlainTextEdit,QLineEdit,QListWidget,QMessageBox,QFormLayout,QGroupBox,QComboBox)

from actions.whatsapp_wa.importer import import_txt, import_text
from actions.whatsapp_wa.store import overview, search_messages
from actions.whatsapp_wa.intelligence import analyse_imported_messages

class NovaWADialog(QDialog):
    """Local-first NOVA WA workspace. Personal WhatsApp is never connected directly."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("NOVA WA — Conversation Intelligence")
        self.resize(1080,760)
        self.setStyleSheet("""
          QDialog,QWidget{background:#061019;color:#d8f7ff;font-family:'Segoe UI';}
          QTabWidget::pane{border:1px solid #17475a;border-radius:12px;}
          QTabBar::tab{background:#0a1b27;color:#8fcbd8;padding:11px 16px;border:1px solid #153c4c;}
          QTabBar::tab:selected{background:#103044;color:#70edff;}
          QPushButton{background:#0b2635;border:1px solid #176078;border-radius:9px;padding:9px 13px;color:#9df3ff;font-weight:700;}
          QPushButton:hover{background:#104057;}
          QLineEdit,QPlainTextEdit,QListWidget{background:#030b12;border:1px solid #17475a;border-radius:8px;padding:9px;color:#e4fbff;}
          QLabel#muted{color:#78a5b4;}
        """)
        root=QVBoxLayout(self)
        head=QHBoxLayout()
        title=QLabel("◉  NOVA WA")
        title.setStyleSheet("font-size:24px;font-weight:800;color:#80efff;")
        head.addWidget(title); head.addStretch()
        self.status=QLabel("PERSONAL IMPORT • LOCAL STORAGE")
        self.status.setObjectName("muted"); head.addWidget(self.status)
        root.addLayout(head)
        intro=QLabel("Manage imported personal conversations and prepare a separate official WhatsApp Business integration.")
        intro.setObjectName("muted"); root.addWidget(intro)
        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)
        self._build_overview(); self._build_import(); self._build_memory(); self._build_modules()
        self.refresh_overview()

    def _build_overview(self):
        page=QWidget(); layout=QVBoxLayout(page)
        title=QLabel("COMMAND CENTER"); title.setStyleSheet("font-size:15px;font-weight:800;color:#68eaff;")
        layout.addWidget(title)
        self.stats=QLabel(); self.stats.setStyleSheet("font-size:18px;padding:18px;background:#0a1b27;border:1px solid #17475a;border-radius:12px;")
        layout.addWidget(self.stats)
        note=QLabel("Personal WhatsApp remains unchanged. Import only chats or selected messages that you choose to share.")
        note.setWordWrap(True); note.setObjectName("muted"); layout.addWidget(note)
        refresh=QPushButton("Refresh dashboard"); refresh.clicked.connect(self.refresh_overview); layout.addWidget(refresh)
        layout.addStretch()
        self.tabs.addTab(page,"Command Center")

    def _build_import(self):
        page=QWidget(); layout=QVBoxLayout(page)
        title=QLabel("IMPORT PERSONAL WHATSAPP"); title.setStyleSheet("font-size:15px;font-weight:800;color:#68eaff;")
        layout.addWidget(title)
        info=QLabel("Export a chat from WhatsApp as a .txt file, or paste selected messages. Files are stored locally; no WhatsApp login or QR pairing is used.")
        info.setWordWrap(True); info.setObjectName("muted"); layout.addWidget(info)
        row=QHBoxLayout()
        self.chat_name=QLineEdit(); self.chat_name.setPlaceholderText("Conversation/contact label (optional)")
        row.addWidget(self.chat_name,1)
        pick=QPushButton("Import .TXT export"); pick.clicked.connect(self.choose_file); row.addWidget(pick)
        layout.addLayout(row)
        self.paste=QPlainTextEdit(); self.paste.setPlaceholderText("Paste selected WhatsApp messages here…")
        layout.addWidget(self.paste,1)
        actions=QHBoxLayout()
        paste_btn=QPushButton("Import pasted messages"); paste_btn.clicked.connect(self.import_pasted); actions.addWidget(paste_btn)
        analyse=QPushButton("Analyse imported chats"); analyse.clicked.connect(self.analyse); actions.addWidget(analyse)
        layout.addLayout(actions)
        self.import_result=QLabel("No import performed yet."); self.import_result.setWordWrap(True); self.import_result.setObjectName("muted")
        layout.addWidget(self.import_result)
        self.tabs.addTab(page,"Import Center")

    def _build_memory(self):
        page=QWidget(); layout=QVBoxLayout(page)
        title=QLabel("LIFE MEMORY SEARCH"); title.setStyleSheet("font-size:15px;font-weight:800;color:#68eaff;")
        layout.addWidget(title)
        row=QHBoxLayout(); self.query=QLineEdit(); self.query.setPlaceholderText("Search imported conversations…")
        self.query.returnPressed.connect(self.search); row.addWidget(self.query,1)
        btn=QPushButton("Search"); btn.clicked.connect(self.search); row.addWidget(btn); layout.addLayout(row)
        self.results=QListWidget(); layout.addWidget(self.results,1)
        self.tabs.addTab(page,"Life Memory")

    def _build_modules(self):
        from PyQt6.QtWidgets import QSplitter
        self.module_lists={}
        specs=[
          ("Smart Inbox","smart_inbox","Latest imported messages and items that may need attention."),
          ("Scam Detector","scams","Local risk indicators. These are warnings, not definitive fraud verdicts."),
          ("Action Engine","tasks","Suggested tasks extracted from messages; approve only after review."),
          ("Relationship Intelligence","relationships","Source-linked possible promises and commitments."),
          ("Communication Analytics","analytics","Metrics calculated from imported data only."),
          ("Automation Studio","automation","Official WhatsApp Business API channel; personal WhatsApp is never automated."),
          ("Daily Briefing","briefing","A compact summary of outstanding items in the imported dataset.")
        ]
        for label,key,description in specs:
            page=QWidget(); box=QVBoxLayout(page)
            heading=QLabel(label.upper()); heading.setStyleSheet("font-size:15px;font-weight:800;color:#68eaff;")
            box.addWidget(heading)
            note=QLabel(description); note.setWordWrap(True); note.setObjectName("muted"); box.addWidget(note)
            listing=QListWidget(); box.addWidget(listing,1); self.module_lists[key]=listing
            row=QHBoxLayout()
            refresh=QPushButton("Refresh"); refresh.clicked.connect(lambda checked=False,k=key:self.refresh_module(k))
            row.addWidget(refresh)
            if key=="tasks":
                approve=QPushButton("Approve selected task")
                approve.clicked.connect(self.approve_selected_task); row.addWidget(approve)
            box.addLayout(row)
            self.tabs.addTab(page,label)
        # Language Bridge is interactive and uses the existing NOVA provider configuration.
        page=QWidget(); box=QVBoxLayout(page)
        heading=QLabel("LANGUAGE BRIDGE"); heading.setStyleSheet("font-size:15px;font-weight:800;color:#68eaff;")
        box.addWidget(heading)
        self.language_input=QPlainTextEdit(); self.language_input.setPlaceholderText("Paste a message in Punjabi, Hindi, English or Hinglish…"); box.addWidget(self.language_input,1)
        row=QHBoxLayout(); self.language_target=QComboBox(); self.language_target.addItems(["English","Hindi","Punjabi","Roman Punjabi"])
        row.addWidget(self.language_target)
        translate=QPushButton("Translate with NOVA AI"); translate.clicked.connect(self.translate_text); row.addWidget(translate); box.addLayout(row)
        self.language_output=QPlainTextEdit(); self.language_output.setReadOnly(True); self.language_output.setPlaceholderText("Translation appears here…"); box.addWidget(self.language_output,1)
        self.tabs.addTab(page,"Language Bridge")
        self.refresh_all_modules()

    def refresh_all_modules(self):
        for key in self.module_lists: self.refresh_module(key)

    def refresh_module(self,key):
        listing=self.module_lists.get(key)
        if listing is None: return
        listing.clear()
        try:
            from actions.whatsapp_wa.store import connect
            with connect() as db:
                if key=="smart_inbox":
                    rows=db.execute("SELECT m.id,m.timestamp,m.sender,m.text,c.title FROM messages m JOIN conversations c ON c.id=m.conversation_id ORDER BY m.id DESC LIMIT 150").fetchall()
                    for x in rows:
                        flag="  •  NEEDS ATTENTION" if "?" in (x["text"] or "") or any(w in (x["text"] or "").lower() for w in ("urgent","please send","deadline","call me")) else ""
                        listing.addItem(f"#{x['id']}  {x['timestamp'] or 'date unknown'}  |  {x['title']} / {x['sender']}{flag}\n{x['text'][:450]}")
                elif key=="scams":
                    rows=db.execute("SELECT r.level,r.explanation,r.indicators,m.sender,m.text,m.timestamp FROM risk_findings r JOIN messages m ON m.id=r.source_message_id ORDER BY r.id DESC LIMIT 150").fetchall()
                    for x in rows: listing.addItem(f"{x['level'].upper()} • {x['sender']} • {x['timestamp'] or 'date unknown'}\n{x['explanation']}\n{x['text'][:350]}")
                elif key=="tasks":
                    rows=db.execute("SELECT t.id,t.title,t.status,m.sender,m.text FROM tasks t JOIN messages m ON m.id=t.source_message_id ORDER BY t.id DESC LIMIT 150").fetchall()
                    for x in rows: listing.addItem(f"Task #{x['id']} [{x['status']}] {x['title']}\nSource: {x['sender']} — {x['text'][:300]}")
                elif key=="relationships":
                    rows=db.execute("SELECT c.description,c.direction,c.status,m.sender,m.timestamp FROM commitments c JOIN messages m ON m.id=c.source_message_id ORDER BY c.id DESC LIMIT 150").fetchall()
                    for x in rows: listing.addItem(f"{x['direction'].upper()} • {x['status']} • {x['sender']} • {x['timestamp'] or 'date unknown'}\n{x['description']}")
                elif key=="analytics":
                    vals={"Imported messages":db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],"Conversations":db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],"Contacts":db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],"Suggested tasks":db.execute("SELECT COUNT(*) FROM tasks WHERE status='suggested'").fetchone()[0],"Open commitments":db.execute("SELECT COUNT(*) FROM commitments WHERE status='open'").fetchone()[0],"Risk indicators":db.execute("SELECT COUNT(*) FROM risk_findings").fetchone()[0]}
                    for k,v in vals.items(): listing.addItem(f"{k}: {v}")
                elif key=="automation":
                    import os
                    listing.addItem("Channel: Separate WhatsApp Business Cloud API")
                    listing.addItem("Automation enabled: "+os.getenv("NOVA_WA_AUTOMATION_ENABLED","false"))
                    listing.addItem("Allowlisted senders configured: "+str(len([x for x in os.getenv("NOVA_WA_ALLOWED_SENDERS","").split(",") if x.strip()])))
                    listing.addItem("Access token configured: "+("yes" if os.getenv("NOVA_WA_ACCESS_TOKEN") else "no"))
                    listing.addItem("Phone Number ID configured: "+("yes" if os.getenv("NOVA_WA_PHONE_NUMBER_ID") else "no"))
                    rows=db.execute("SELECT event_type,detail,created_at FROM automation_events ORDER BY id DESC LIMIT 100").fetchall()
                    for x in rows: listing.addItem(f"{x['created_at']} • {x['event_type']}\n{x['detail']}")
                    listing.addItem("Auto replies remain disabled until Meta webhook, sender allowlist, model and safety policy are configured and tested.")
                elif key=="briefing":
                    tasks=db.execute("SELECT COUNT(*) FROM tasks WHERE status='suggested'").fetchone()[0]
                    commitments=db.execute("SELECT COUNT(*) FROM commitments WHERE status='open'").fetchone()[0]
                    risks=db.execute("SELECT COUNT(*) FROM risk_findings").fetchone()[0]
                    listing.addItem(f"Suggested tasks to review: {tasks}")
                    listing.addItem(f"Possible open commitments: {commitments}")
                    listing.addItem(f"Risk indicators to inspect: {risks}")
                    rows=db.execute("SELECT m.sender,m.text,m.timestamp FROM messages m WHERE m.text LIKE '%?%' ORDER BY m.id DESC LIMIT 10").fetchall()
                    for x in rows: listing.addItem(f"Potential unanswered question • {x['sender']} • {x['timestamp'] or 'date unknown'}\n{x['text'][:300]}")
            if listing.count()==0: listing.addItem("No records yet. Import a WhatsApp chat and run analysis first.")
        except Exception as exc:
            listing.addItem(f"Could not load this view: {exc}")

    def approve_selected_task(self):
        item=self.module_lists["tasks"].currentItem()
        if not item: return
        import re
        match=re.search(r"Task #(\\d+)",item.text())
        if not match: return
        try:
            from actions.whatsapp_wa.intelligence import approve_task
            if approve_task(int(match.group(1))):
                QMessageBox.information(self,"NOVA WA","Task approved.")
            self.refresh_module("tasks"); self.refresh_overview()
        except Exception as exc: QMessageBox.warning(self,"NOVA WA",str(exc))

    def translate_text(self):
        try:
            from actions.whatsapp_wa.language import translate
            result=translate(self.language_input.toPlainText(),self.language_target.currentText())
            self.language_output.setPlainText(result)
        except Exception as exc: QMessageBox.warning(self,"Language Bridge",str(exc))

    def refresh_overview(self):
        data=overview()
        self.stats.setText(f"Imports: {data['imports']}     Messages: {data['messages']}     Contacts: {data['contacts']}\nSuggested tasks: {data['tasks']}     Risk indicators: {data['risks']}")

    def choose_file(self):
        path,_=QFileDialog.getOpenFileName(self,"Select WhatsApp chat export","","WhatsApp text export (*.txt)")
        if not path: return
        try:
            result=import_txt(path,self.chat_name.text().strip() or None)
            self.import_result.setText(f"Imported {result['messages']} messages from {result['title']}." if not result["duplicate"] else "This exact export has already been imported.")
            self.refresh_overview()
        except Exception as exc:
            QMessageBox.warning(self,"Import failed",str(exc))

    def import_pasted(self):
        try:
            result=import_text(self.paste.toPlainText(),self.chat_name.text().strip() or "Pasted conversation")
            self.import_result.setText(f"Imported {result['messages']} selected messages." if not result["duplicate"] else "This exact selection has already been imported.")
            self.paste.clear(); self.refresh_overview()
        except Exception as exc:
            QMessageBox.warning(self,"Import failed",str(exc))

    def analyse(self):
        try:
            result=analyse_imported_messages()
            self.import_result.setText(f"Analysis complete. Risk indicators: {result['risks']}; task suggestions: {result['tasks']}; possible commitments: {result['commitments']}. Review all suggestions.")
            self.refresh_overview()
        except Exception as exc:
            QMessageBox.warning(self,"Analysis failed",str(exc))

    def search(self):
        self.results.clear()
        try:
            rows=search_messages(self.query.text())
            for row in rows:
                self.results.addItem(f"{row['timestamp'] or 'Date unknown'} | {row['sender']} | {row['title']}\n{row['text'][:700]}")
            if not rows: self.results.addItem("No matching imported messages.")
        except Exception as exc:
            QMessageBox.warning(self,"Search failed",str(exc))
