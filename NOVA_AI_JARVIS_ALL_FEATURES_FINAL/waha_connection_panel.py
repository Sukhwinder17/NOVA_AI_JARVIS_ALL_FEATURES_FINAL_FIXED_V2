from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QPlainTextEdit, QMessageBox, QGroupBox, QFormLayout, QSizePolicy
)

from actions.whatsapp_wa import waha_client

PROJECT_ROOT = Path(__file__).resolve().parent


class WahaConnectionPanel(QWidget):
    """Local WAHA connection panel. Sending remains a deliberate user action."""
    def __init__(self, parent=None, on_import_refresh=None):
        super().__init__(parent)
        self.on_import_refresh = on_import_refresh
        root = QVBoxLayout(self)
        warning = QLabel(
            "WAHA uses an unofficial WhatsApp linked-device integration. WhatsApp may restrict accounts. "
            "Use a secondary number if possible. NOVA does not auto-reply or send messages on its own."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#ffc47a;background:#24180c;border:1px solid #75502b;border-radius:9px;padding:10px;")
        root.addWidget(warning)

        settings_box = QGroupBox("WAHA local connection")
        form = QFormLayout(settings_box)
        cfg = waha_client.settings()
        self.url = QLineEdit(cfg["url"])
        self.session = QLineEdit(cfg["session"])
        self.api_key = QLineEdit(cfg["api_key"])
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.dashboard_password = QLineEdit(cfg.get("dashboard_password", ""))
        self.dashboard_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.webhook_token = QLineEdit(cfg["webhook_token"])
        self.webhook_token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Local API URL", self.url)
        form.addRow("Session name", self.session)
        form.addRow("API key", self.api_key)
        form.addRow("Dashboard password", self.dashboard_password)
        form.addRow("Inbound sync token", self.webhook_token)
        root.addWidget(settings_box)

        buttons = QHBoxLayout()
        save = QPushButton("Generate keys / Save settings")
        save.clicked.connect(self.save_settings)
        buttons.addWidget(save)
        docker = QPushButton("Start WAHA (Docker)")
        docker.clicked.connect(self.start_docker)
        buttons.addWidget(docker)
        check = QPushButton("Check connection")
        check.clicked.connect(self.check_api)
        buttons.addWidget(check)
        root.addLayout(buttons)

        pair_row = QHBoxLayout()
        pair = QPushButton("Start / Link WhatsApp")
        pair.clicked.connect(self.link_session)
        pair_row.addWidget(pair)
        qr = QPushButton("Refresh QR")
        qr.clicked.connect(self.refresh_qr)
        pair_row.addWidget(qr)
        stop = QPushButton("Stop session")
        stop.clicked.connect(self.stop_session)
        pair_row.addWidget(stop)
        root.addLayout(pair_row)

        sync_row = QHBoxLayout()
        sync = QPushButton("Sync recent chats into NOVA (up to 20 chats × 30 messages)")
        sync.clicked.connect(self.sync_chats)
        sync_row.addWidget(sync)
        dashboard = QPushButton("Open WAHA Dashboard")
        dashboard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.url.text().rstrip("/") + "/dashboard")))
        sync_row.addWidget(dashboard)
        root.addLayout(sync_row)

        self.qr_label = QLabel("QR code will appear here after WAHA starts the session.")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setMinimumHeight(260)
        self.qr_label.setStyleSheet("background:#f7f7f7;color:#1b1b1b;border:1px solid #17475a;border-radius:10px;padding:8px;")
        root.addWidget(self.qr_label)

        send_box = QGroupBox("Manual message test (no automatic replies)")
        send_form = QFormLayout(send_box)
        self.chat_id = QLineEdit()
        self.chat_id.setPlaceholderText("e.g. 9198XXXXXXXX@c.us")
        self.message = QPlainTextEdit()
        self.message.setMaximumHeight(75)
        self.message.setPlaceholderText("Message to send only when you click Send")
        send_form.addRow("WhatsApp chat ID", self.chat_id)
        send_form.addRow("Message", self.message)
        send_btn = QPushButton("Send this message")
        send_btn.clicked.connect(self.send_message)
        send_form.addRow(send_btn)
        root.addWidget(send_box)

        self.status = QLabel("Save settings, start Docker, then link your WhatsApp device.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#78a5b4;padding:5px;")
        root.addWidget(self.status)
        root.addStretch()

    def _ensure_settings(self):
        if not self.api_key.text().strip():
            self.api_key.setText(secrets.token_hex(32))
        if not self.dashboard_password.text().strip():
            self.dashboard_password.setText(secrets.token_urlsafe(24))
        if not self.webhook_token.text().strip():
            self.webhook_token.setText(secrets.token_urlsafe(32))

    def save_settings(self):
        self._ensure_settings()
        try:
            waha_client.save_settings({
                "url": self.url.text(),
                "session": self.session.text(),
                "api_key": self.api_key.text(),
                "dashboard_password": self.dashboard_password.text(),
                "webhook_token": self.webhook_token.text(),
            })
            self.status.setText("Settings saved to the local .env file. API/dashboard keys were generated if empty.")
            QMessageBox.information(self, "WAHA settings", "Saved locally in .env. Keep this file private; it contains access keys.")
        except Exception as exc:
            QMessageBox.warning(self, "WAHA settings", str(exc))

    def start_docker(self):
        self._ensure_settings()
        try:
            waha_client.save_settings({
                "url": self.url.text(),
                "session": self.session.text(),
                "api_key": self.api_key.text(),
                "dashboard_password": self.dashboard_password.text(),
                "webhook_token": self.webhook_token.text(),
            })
            self.status.setText("Starting WAHA Docker container…")
            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose.waha.yml", "up", "-d"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=180,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            if result.returncode:
                raise RuntimeError(output[-2500:] or "docker compose failed")
            self.status.setText("WAHA container started. Click Check connection, then Start / Link WhatsApp.")
            QMessageBox.information(self, "WAHA", "WAHA is starting in Docker. It may take a minute on the first run while the image downloads.")
        except Exception as exc:
            QMessageBox.warning(self, "Could not start WAHA", str(exc))

    def check_api(self):
        try:
            sessions = waha_client.check_connection()
            self.status.setText(f"WAHA API connected. Sessions response: {sessions}")
        except Exception as exc:
            QMessageBox.warning(self, "WAHA connection", str(exc))

    def _start_receiver(self):
        # The container reaches the Windows host through host.docker.internal.
        try:
            import requests
            response = requests.get("http://127.0.0.1:8788/health", timeout=1.5)
            if response.ok:
                return
        except Exception:
            pass
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "actions.whatsapp_wa.waha_webhook:app", "--host", "0.0.0.0", "--port", "8788"],
            cwd=str(PROJECT_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True,
        )

    def link_session(self):
        answer = QMessageBox.warning(
            self, "Link WhatsApp to WAHA",
            "WAHA is an unofficial WhatsApp linked-device client. This may cause WhatsApp account restrictions. "
            "Continue only if you accept this risk; a secondary number is recommended.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._ensure_settings()
            waha_client.save_settings({
                "url": self.url.text(), "session": self.session.text(),
                "api_key": self.api_key.text(), "dashboard_password": self.dashboard_password.text(),
                "webhook_token": self.webhook_token.text(),
            })
            self._start_receiver()
            detail = waha_client.create_or_start_session("http://host.docker.internal:8788/waha/events")
            self.status.setText(f"Session response: {detail}\nWAHA may need a few seconds to generate the QR. It will refresh automatically.")
            QTimer.singleShot(3500, self.refresh_qr)
        except Exception as exc:
            QMessageBox.warning(self, "WAHA link", str(exc))

    def refresh_qr(self):
        try:
            data = waha_client.get_qr_image()
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                raise RuntimeError("WAHA returned a QR image that Qt could not read. Check the session status and try again.")
            self.qr_label.setPixmap(pixmap.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.status.setText("Scan this QR in WhatsApp → Settings/⋮ → Linked devices → Link a device.")
        except Exception as exc:
            self.status.setText(str(exc))

    def stop_session(self):
        try:
            from urllib.parse import quote
            name = quote(self.session.text().strip(), safe="")
            waha_client._request("POST", f"/api/sessions/{name}/stop", json={})
            self.qr_label.setText("Session stopped. Your linked device may remain linked until you log out from WhatsApp Linked Devices.")
            self.status.setText("WAHA session stopped.")
        except Exception as exc:
            QMessageBox.warning(self, "Stop session", str(exc))

    def send_message(self):
        answer = QMessageBox.question(
            self, "Send WhatsApp message",
            "Send this message from the linked WhatsApp account?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = waha_client.send_text(self.chat_id.text(), self.message.toPlainText())
            self.status.setText(f"Message sent by explicit click. API response: {result}")
            self.message.clear()
        except Exception as exc:
            QMessageBox.warning(self, "Send message", str(exc))


    def sync_chats(self):
        answer = QMessageBox.question(
            self, "Sync WhatsApp chats",
            "NOVA will read up to 20 recent chats and up to 30 messages per chat from WAHA, "
            "then store their text locally in the NOVA WA database. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.status.setText("Syncing recent WhatsApp chats into NOVA. Please wait…")
            result = waha_client.sync_recent_chats(chat_limit=20, messages_per_chat=30)
            self.status.setText(
                f"Sync finished: {result['chats_synced']} chats, {result['messages_added']} new messages. "
                f"Errors: {len(result['errors'])}"
            )
            if self.on_import_refresh:
                self.on_import_refresh()
            if result["errors"]:
                QMessageBox.warning(self, "Some chats could not sync", "\\n".join(result["errors"][:5]))
            else:
                QMessageBox.information(self, "NOVA WA sync", self.status.text())
        except Exception as exc:
            QMessageBox.warning(self, "Chat sync failed", str(exc))
