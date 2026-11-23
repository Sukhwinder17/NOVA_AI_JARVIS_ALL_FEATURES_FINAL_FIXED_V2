from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTabWidget,
    QWidget,QFileDialog,QPlainTextEdit,QLineEdit,QListWidget,QMessageBox,QFormLayout,QGroupBox)

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
        specs=[
          ("Smart Inbox","Prioritisation will use imported-message timestamps and detected unanswered requests. Live sync is not available for personal imports."),
          ("Scam Detector","First-pass local indicators are available after analysis. Findings are warnings, not definitive fraud determinations."),
          ("Action Engine","Tasks extracted from imported messages require user review before approval or scheduling."),
          ("Language Bridge","Translation and multilingual reply drafting will connect to NOVA's existing AI provider layer in the next integration step."),
          ("Relationship Intelligence","Promise and preference records will be source-linked and user-correctable."),
          ("Communication Analytics","Metrics will be calculated only from imported data and clearly labelled with the import date."),
          ("Automation Studio","Separate WhatsApp Business Cloud API only. Personal WhatsApp automatic sending is intentionally unsupported.")
        ]
        for name,description in specs:
            page=QWidget(); box=QVBoxLayout(page)
            heading=QLabel(name.upper()); heading.setStyleSheet("font-size:15px;font-weight:800;color:#68eaff;")
            box.addWidget(heading)
            text=QLabel(description); text.setWordWrap(True); text.setObjectName("muted"); box.addWidget(text)
            box.addStretch()
            self.tabs.addTab(page,name)

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
