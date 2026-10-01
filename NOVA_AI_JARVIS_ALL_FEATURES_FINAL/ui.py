from __future__ import annotations

import math
import random
import threading
import html
import re

from memory.conversation_history import load_history

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QRadialGradient, QFont, QLinearGradient, QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QFrame,
    QComboBox,
    QSizePolicy,
    QInputDialog,
    QLineEdit,
)


class SignalBus(QObject):
    reply = pyqtSignal(str, str)
    state = pyqtSignal(str)
    error = pyqtSignal(str)
    voice_text = pyqtSignal(str)


class Worker(threading.Thread):
    def __init__(self, fn):
        super().__init__(daemon=True)
        self.fn = fn

    def run(self):
        try:
            self.fn()
        except Exception as exc:
            print("[NOVA UI]", exc)


class RobotCore(QWidget):
    """Animated NOVA robot core rendered procedurally with Qt — no image asset required."""

    def __init__(self):
        super().__init__()
        self.phase = 0.0
        self.amp = 0.0
        self.state = "READY"
        self.expression = "NEUTRAL"
        self.blink = 0.0
        self.setMinimumSize(390, 390)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def set_state(self, state):
        self.state = str(state).upper()
        self.update()

    def set_expression(self, expression):
        value = str(expression).upper().strip()
        allowed = {"NEUTRAL", "HAPPY", "CURIOUS", "CONFUSED", "ALERT", "SAD"}
        self.expression = value if value in allowed else "NEUTRAL"
        self.update()

    def set_amp(self, amp):
        self.amp = max(0.0, min(1.0, float(amp)))
        self.update()

    def tick(self):
        self.phase = (self.phase + 0.055 + 0.085 * self.amp) % math.tau
        self.amp *= 0.90
        # Natural periodic blink without adding another timer.
        blink_cycle = self.phase % 5.8
        self.blink = max(0.0, 1.0 - abs(blink_cycle - 5.45) / 0.16) if blink_cycle > 5.29 else 0.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2
        bob = math.sin(self.phase * 1.65) * 6.0
        sway = math.sin(self.phase * 0.82) * 3.0
        cy = h / 2 - 8 + bob
        scale = min(w, h) / 430.0
        pulse = 1.0 + 0.035 * math.sin(self.phase * 2.4) + 0.07 * self.amp

        # Keep the existing NOVA Core panel and give the robot its own dark stage.
        p.fillRect(self.rect(), QColor("#020308"))

        # Soft cyan holographic aura.
        aura = QRadialGradient(cx, cy + 25 * scale, 175 * scale)
        aura.setColorAt(0.0, QColor(0, 220, 255, 30 + int(35 * self.amp)))
        aura.setColorAt(0.55, QColor(40, 110, 255, 12))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(aura))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - 175 * scale, cy - 150 * scale, 350 * scale, 350 * scale))

        # Holographic floor ring.
        ring_y = cy + 170 * scale
        for width, alpha in ((12, 20), (6, 45), (2, 150)):
            p.setPen(QPen(QColor(70, 235, 255, alpha), width * scale))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - 92 * scale, ring_y - 13 * scale, 184 * scale, 28 * scale))

        # Ground shadow.
        shadow = QRadialGradient(cx, ring_y, 72 * scale)
        shadow.setColorAt(0.0, QColor(0, 0, 0, 120))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(shadow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - 90 * scale, ring_y - 18 * scale, 180 * scale, 36 * scale))

        # Robot proportions.
        head_w, head_h = 170 * scale, 126 * scale
        head_x, head_y = cx - head_w / 2 + sway, cy - 135 * scale
        body_w, body_h = 104 * scale, 86 * scale
        body_x, body_y = cx - body_w / 2, cy - 12 * scale

        # Antenna / side ear lights.
        for sx in (-1, 1):
            ex = cx + sx * (head_w / 2 + 13 * scale)
            p.setPen(QPen(QColor(255, 151, 35, 235), 9 * scale))
            p.drawLine(QPointF(ex, head_y + 22 * scale), QPointF(ex, head_y + 82 * scale))
            p.setPen(QPen(QColor(72, 235, 255, 190 + int(45 * self.amp)), 3 * scale))
            p.drawLine(QPointF(ex, head_y + 24 * scale), QPointF(ex, head_y + 76 * scale))

        # Head: orange toy-like shell with depth gradient.
        head_grad = QLinearGradient(head_x, head_y, head_x, head_y + head_h)
        head_grad.setColorAt(0.0, QColor("#ffb02e"))
        head_grad.setColorAt(0.35, QColor("#ff8b16"))
        head_grad.setColorAt(1.0, QColor("#d9570b"))
        p.setBrush(QBrush(head_grad))
        p.setPen(QPen(QColor("#ffbf45"), 2 * scale))
        p.drawRoundedRect(QRectF(head_x, head_y, head_w, head_h), 30 * scale, 30 * scale)

        # Top reflective panels.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(255, 245, 210, 220)))
        for i in (-1, 0, 1):
            p.drawRoundedRect(QRectF(cx + i * 24 * scale - 8 * scale, head_y + 9 * scale,
                                     16 * scale, 8 * scale), 3 * scale, 3 * scale)

        # Face glass.
        face_x, face_y = cx - 62 * scale, head_y + 34 * scale
        face_w, face_h = 124 * scale, 72 * scale
        face_grad = QLinearGradient(face_x, face_y, face_x, face_y + face_h)
        face_grad.setColorAt(0.0, QColor("#15273a"))
        face_grad.setColorAt(1.0, QColor("#050b13"))
        p.setBrush(QBrush(face_grad))
        p.setPen(QPen(QColor(35, 85, 110, 220), 1.5 * scale))
        p.drawRoundedRect(QRectF(face_x, face_y, face_w, face_h), 19 * scale, 19 * scale)

        # Subtle face scanlines.
        p.setPen(QPen(QColor(95, 200, 235, 18), 1))
        for y in range(int(face_y + 8 * scale), int(face_y + face_h - 4 * scale), max(5, int(6 * scale))):
            p.drawLine(QPointF(face_x + 8 * scale, y), QPointF(face_x + face_w - 8 * scale, y))

        # Expressive eyes: blink + state/emotion driven poses.
        eye_y = face_y + 32 * scale
        if self.state == "LISTENING":
            eye_scale = 1.12 + 0.10 * math.sin(self.phase * 4)
        elif self.state == "THINKING":
            eye_scale = 0.84
        elif self.expression == "HAPPY":
            eye_scale = 0.92
        elif self.expression == "CURIOUS":
            eye_scale = 1.06 + 0.04 * math.sin(self.phase * 2)
        elif self.expression == "CONFUSED":
            eye_scale = 0.90
        elif self.expression == "ALERT":
            eye_scale = 1.18
        else:
            eye_scale = 1.0 + 0.035 * math.sin(self.phase * 2)

        # Blink is a fast vertical squeeze.
        eye_y_scale = max(0.08, 1.0 - self.blink * 0.92)
        for idx, ex in enumerate((cx - 28 * scale + sway * 0.15, cx + 28 * scale + sway * 0.15)):
            er = 10 * scale * eye_scale
            if self.expression == "SAD":
                eye_y_pos = eye_y + 3 * scale
            elif self.expression == "CURIOUS" and idx == 1:
                eye_y_pos = eye_y - 2 * scale
            else:
                eye_y_pos = eye_y

            glow = QRadialGradient(ex, eye_y_pos, er * 1.8)
            glow.setColorAt(0.0, QColor(220, 255, 255, 235))
            glow.setColorAt(0.45, QColor(80, 240, 255, 160))
            glow.setColorAt(1.0, QColor(0, 210, 255, 0))
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(ex - er * 1.8, eye_y_pos - er * 1.8,
                                 er * 3.6, er * 3.6))

            p.setBrush(QBrush(QColor("#f3ffff")))
            p.drawEllipse(QRectF(ex - er, eye_y_pos - er * eye_y_scale,
                                 er * 2, er * 2 * eye_y_scale))

        # Animated expressive mouth.
        mouth_w = 18 * scale
        if self.state == "SPEAKING":
            mouth_h = (4 + 20 * (0.5 + 0.5 * math.sin(self.phase * 7))) * scale
        elif self.expression == "HAPPY":
            mouth_w, mouth_h = 22 * scale, 7 * scale
        elif self.expression == "CONFUSED":
            mouth_w, mouth_h = 13 * scale, 4 * scale
        elif self.expression == "SAD":
            mouth_w, mouth_h = 16 * scale, 3 * scale
        else:
            mouth_h = 4 * scale

        p.setBrush(QBrush(QColor("#e8ffff")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(cx - mouth_w / 2 + sway * 0.1,
                                 face_y + 51 * scale - mouth_h / 2,
                                 mouth_w, mouth_h), 4 * scale, 4 * scale)

        # Neck.
        p.setBrush(QBrush(QColor("#17222a")))
        p.drawRoundedRect(QRectF(cx - 14 * scale, head_y + head_h - 3 * scale, 28 * scale, 20 * scale),
                          8 * scale, 8 * scale)

        # Body shell.
        body_grad = QLinearGradient(body_x, body_y, body_x, body_y + body_h)
        body_grad.setColorAt(0.0, QColor("#ff9b1c"))
        body_grad.setColorAt(1.0, QColor("#e7630d"))
        p.setBrush(QBrush(body_grad))
        p.setPen(QPen(QColor("#ffb53b"), 2 * scale))
        p.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), 26 * scale, 26 * scale)

        # Chest AI core.
        core_r = 17 * scale * pulse
        cg = QRadialGradient(cx, body_y + 39 * scale, core_r * 2.4)
        cg.setColorAt(0.0, QColor(235, 255, 255, 255))
        cg.setColorAt(0.25, QColor(60, 235, 255, 245))
        cg.setColorAt(1.0, QColor(0, 140, 255, 0))
        p.setBrush(QBrush(cg))
        p.setPen(QPen(QColor(120, 250, 255, 180), 1.5 * scale))
        p.drawEllipse(QRectF(cx - core_r, body_y + 39 * scale - core_r,
                              core_r * 2, core_r * 2))

        # Arms: gentle idle sway; active expressions get more personality.
        arm_y = body_y + 18 * scale
        for sx in (-1, 1):
            shoulder_x = cx + sx * 62 * scale
            wave = 0.0
            if self.expression == "HAPPY" and sx > 0:
                wave = math.sin(self.phase * 3.0) * 14 * scale
            elif self.state == "LISTENING":
                wave = math.sin(self.phase * 2.0) * 5 * scale
            elbow_x = cx + sx * 82 * scale
            hand_x = cx + sx * 78 * scale
            p.setPen(QPen(QColor("#f27b12"), 23 * scale))
            p.drawLine(QPointF(shoulder_x, arm_y), QPointF(elbow_x, arm_y + 42 * scale + wave))
            p.setPen(QPen(QColor("#ff9b1c"), 20 * scale))
            p.drawLine(QPointF(elbow_x, arm_y + 42 * scale + wave),
                       QPointF(hand_x, arm_y + 66 * scale + wave))
            p.setBrush(QBrush(QColor("#17222a")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(elbow_x - 9 * scale, arm_y + 33 * scale + wave,
                                 18 * scale, 18 * scale))
            p.setBrush(QBrush(QColor("#ff9a18")))
            p.drawRoundedRect(QRectF(hand_x - 12 * scale, arm_y + 58 * scale + wave,
                                     24 * scale, 30 * scale), 10 * scale, 10 * scale)

        # Waist.
        p.setBrush(QBrush(QColor("#101920")))
        p.drawRoundedRect(QRectF(cx - 45 * scale, body_y + body_h - 4 * scale,
                                 90 * scale, 27 * scale), 10 * scale, 10 * scale)

        # Legs.
        leg_y = body_y + body_h + 12 * scale
        for sx in (-1, 1):
            lx = cx + sx * 31 * scale
            p.setPen(QPen(QColor("#f47a0e"), 28 * scale))
            p.drawLine(QPointF(lx, leg_y), QPointF(lx + sx * 3 * scale, leg_y + 67 * scale))
            p.setPen(QPen(QColor("#ff9b18"), 25 * scale))
            p.drawLine(QPointF(lx + sx * 3 * scale, leg_y + 58 * scale),
                       QPointF(lx + sx * 5 * scale, leg_y + 91 * scale))
            p.setBrush(QBrush(QColor("#17222a")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(lx - 10 * scale, leg_y + 51 * scale,
                                 20 * scale, 20 * scale))
            p.setBrush(QBrush(QColor("#f58a12")))
            p.drawRoundedRect(QRectF(lx - 19 * scale, leg_y + 78 * scale,
                                     38 * scale, 27 * scale), 11 * scale, 11 * scale)

        # Small status sparks while active.
        if self.state in ("LISTENING", "THINKING", "SPEAKING"):
            for k in range(4):
                a = self.phase * (1.2 + k * 0.05) + k * math.tau / 6
                rr = 126 * scale + 8 * math.sin(self.phase * 2 + k)
                x = cx + math.cos(a) * rr
                y = cy + math.sin(a) * rr * 0.78
                r = (2.0 + self.amp * 2.5) * scale
                p.setBrush(QBrush(QColor(100, 240, 255, 130 + int(90 * self.amp))))
                p.drawEllipse(QRectF(x-r, y-r, r*2, r*2))

        # State label remains in the same place as the old sphere label.
        p.setPen(QColor("#75efff"))
        font = QFont("Segoe UI", 10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.2)
        p.setFont(font)
        p.drawText(QRectF(cx - 120 * scale, cy + 194 * scale, 240 * scale, 30 * scale),
                   Qt.AlignmentFlag.AlignCenter, self.state)
        p.end()


# Backwards-compatible name for any external imports.
Sphere = RobotCore



class ChatBubble(QFrame):
    def __init__(self, who, text):
        super().__init__()
        self.setObjectName("bubbleNova" if who.upper() == "NOVA" else "bubbleUser")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 13)
        layout.setSpacing(5)

        header = QLabel(who.upper())
        header.setObjectName("bubbleWho")
        layout.addWidget(header)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.body.setOpenExternalLinks(False)
        self.body.linkActivated.connect(self.open_link)
        self.body.setObjectName("bubbleBody")
        self.set_body(str(text))
        layout.addWidget(self.body)

    def set_body(self, text):
        """Render URLs and numbered Windows file results as clickable links."""
        lines = str(text).splitlines()
        rendered = []

        for line in lines:
            # NOVA file results: "01. C:\\path\\filename.pdf"
            m = re.match(r"^(\s*\d+\.\s+)([A-Za-z]:\\.*)$", line)
            if m:
                prefix = html.escape(m.group(1), quote=False)
                path = m.group(2).strip()
                name = path.replace("\\", "/").rsplit("/", 1)[-1]
                href = QUrl.fromLocalFile(path).toString()
                rendered.append(
                    prefix
                    + f'<a href="{html.escape(href, quote=True)}">{html.escape(name, quote=False)}</a>'
                )
                continue

            # Split raw text first so normal apostrophes/quotes stay normal.
            parts = re.split(r"(https?://[^\s<]+)", str(line))
            out = []
            for part in parts:
                if re.match(r"^https?://", part):
                    out.append(
                        f'<a href="{html.escape(part, quote=True)}">{html.escape(part, quote=False)}</a>'
                    )
                else:
                    out.append(html.escape(part, quote=False))
            rendered.append("".join(out))

        self.body.setText("<br>".join(rendered))

    def open_link(self, url):
        QDesktopServices.openUrl(QUrl(url))


class CommandChip(QPushButton):
    def __init__(self, text, callback):
        super().__init__(text)
        self.clicked.connect(callback)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class NovaWindow(QMainWindow):
    submit = pyqtSignal(str)

    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator
        orchestrator.ui = self
        self.bus = SignalBus()
        self.history = []
        self.listening = False
        self._tts = None

        self.setWindowTitle("NOVA AI")
        self.resize(1420, 900)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(self.css())

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 18, 24, 20)
        main.setSpacing(14)

        # ---------------- HEADER ----------------
        header = QHBoxLayout()
        header.setSpacing(12)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        brand = QLabel("◉ NOVA AI")
        brand.setObjectName("brand")
        brand_box.addWidget(brand)
        sub = QLabel("PERSONAL INTELLIGENCE  •  LOCAL CONTROL  •  LIVE ACTIONS")
        sub.setObjectName("brandSub")
        brand_box.addWidget(sub)
        header.addLayout(brand_box)
        header.addStretch()

        self.status = QLabel("● READY")
        self.status.setObjectName("status")
        header.addWidget(self.status)

        self.provider = QComboBox()
        self.provider.addItems(["AUTO", "GROQ", "GEMINI", "XKIRO"])
        self.provider.setToolTip("AI provider used for conversation and tool decisions")
        self.provider.setFixedWidth(132)
        header.addWidget(self.provider)
        main.addLayout(header)

        # ---------------- MAIN ----------------
        content = QHBoxLayout()
        content.setSpacing(16)
        main.addLayout(content, 1)

        # Left reactor panel.
        left = QFrame()
        left.setObjectName("reactorPanel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 14)
        ll.setSpacing(8)

        reactor_title = QLabel("NOVA CORE")
        reactor_title.setObjectName("panelTitle")
        reactor_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(reactor_title)

        reactor_sub = QLabel("LOCAL DESKTOP AGENT")
        reactor_sub.setObjectName("panelSub")
        reactor_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(reactor_sub)

        self.sphere = RobotCore()
        ll.addWidget(self.sphere, 1)

        self.activity = QLabel("SYSTEM READY")
        self.activity.setObjectName("activity")
        self.activity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(self.activity)

        hints = QLabel(
            "Find files  •  Open apps  •  Browser control\n"
            "Messages  •  Screen vision  •  Voice  •  DataLens"
        )
        hints.setObjectName("hints")
        hints.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(hints)
        content.addWidget(left, 44)

        # Right conversation panel.
        right = QFrame()
        right.setObjectName("conversationPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(18, 16, 18, 16)
        rl.setSpacing(10)

        top = QHBoxLayout()
        title = QLabel("CONVERSATION")
        title.setObjectName("section")
        top.addWidget(title)
        top.addStretch()
        live = QLabel("LIVE COMMAND CHANNEL")
        live.setObjectName("liveLabel")
        top.addWidget(live)
        rl.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        self.chat = QVBoxLayout(holder)
        self.chat.setContentsMargins(2, 2, 4, 2)
        self.chat.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat.setSpacing(9)
        self.scroll.setWidget(holder)
        rl.addWidget(self.scroll, 1)

        # Quick command strip.
        quick_title = QLabel("QUICK COMMANDS")
        quick_title.setObjectName("quickTitle")
        rl.addWidget(quick_title)
        chips = QHBoxLayout()
        chips.setSpacing(7)
        for label, command in [
            ("FILES", "find my DataLens files"),
            ("YOUTUBE", "open youtube"),
            ("DATALENS", "open datalens"),
            ("WHATSAPP", "open whatsapp"),
            ("VISION", "explain this screen"),
            ("CHECK", "check nova features"),
        ]:
            chip = CommandChip(label, lambda checked=False, c=command: self.run_quick(c))
            chips.addWidget(chip)
        rl.addLayout(chips)

        # Composer.
        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Talk to NOVA — e.g.  open Blender  •  find my DataLens files  •  send hi to Sukhwinder")
        self.input.returnPressed.connect(self.send)
        row.addWidget(self.input, 1)

        self.attach_btn = QPushButton("📎")
        self.attach_btn.setObjectName("attachButton")
        self.attach_btn.setToolTip("Attach a file from your PC to the current task")
        self.attach_btn.clicked.connect(self.select_attachment)
        row.addWidget(self.attach_btn)

        self.listen = QPushButton("◉  LISTEN")
        self.listen.setObjectName("listenButton")
        self.listen.clicked.connect(self.toggle_listen)
        row.addWidget(self.listen)

        send = QPushButton("SEND  ↗")
        send.setObjectName("sendButton")
        send.clicked.connect(self.send)
        row.addWidget(send)
        rl.addLayout(row)

        self.quick = QLabel(
            "CTRL+SPACE  push-to-talk   •   SAY “listen” / “stop listening”   •   “open 3” opens a file result   •   “check features” runs a safe health check"
        )
        self.quick.setObjectName("quick")
        rl.addWidget(self.quick)

        content.addWidget(right, 56)

        previous = load_history(24)
        if previous:
            for item in previous:
                self.add_message("YOU" if item["role"] == "user" else "NOVA", item["content"])
        else:
            self.add_message(
                "NOVA",
                "Hello. I’m NOVA. Tell me what you want done — open an app, find a file, control the browser, send a message, analyze your screen, or just chat.",
            )

        self.bus.reply.connect(self.on_reply)
        self.bus.state.connect(self.on_state)
        self.bus.voice_text.connect(self.on_voice_text)

        try:
            from core.tts_nova import NovaTTS
            self._tts = NovaTTS(self.set_speaking)
        except Exception:
            self._tts = None

        self.show()

    def css(self):
        return """
        QMainWindow, QWidget#root {
            background: #03070c;
            color: #d9f8ff;
            font-family: "Segoe UI";
        }
        #brand {
            font-size: 27px;
            font-weight: 750;
            color: #c4fbff;
            letter-spacing: 2px;
        }
        #brandSub {
            color: #4c8498;
            font-size: 9px;
            letter-spacing: 1.8px;
            margin-top: 2px;
        }
        #status {
            color: #58ffbd;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1px;
            padding: 8px 12px;
            border: 1px solid #164d48;
            border-radius: 12px;
            background: #061714;
        }
        QComboBox {
            background: #07131c;
            border: 1px solid #1b5368;
            border-radius: 10px;
            padding: 8px 11px;
            color: #aaf5ff;
            font-size: 11px;
            font-weight: 700;
        }
        QComboBox:hover { border-color: #27dfff; }
        #reactorPanel, #conversationPanel {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #061019, stop:0.55 #050b12, stop:1 #07131b);
            border: 1px solid #12394b;
            border-radius: 24px;
        }
        #reactorPanel {
            border-color: #104358;
        }
        #panelTitle {
            color: #68eaff;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 3px;
        }
        #panelSub {
            color: #3c7186;
            font-size: 8px;
            letter-spacing: 2px;
        }
        #activity {
            color: #68eaff;
            font-size: 10px;
            letter-spacing: 2px;
            font-weight: 700;
        }
        #hints {
            color: #476d7d;
            font-size: 9px;
            line-height: 1.7;
        }
        #section {
            color: #67eaff;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 2.4px;
        }
        #liveLabel {
            color: #39788b;
            font-size: 8px;
            letter-spacing: 1.5px;
            padding: 5px 9px;
            border: 1px solid #123d4e;
            border-radius: 8px;
        }
        #quickTitle {
            color: #3e7e92;
            font-size: 8px;
            letter-spacing: 1.8px;
            font-weight: 700;
        }
        #quick {
            color: #3c6575;
            font-size: 8px;
            padding-left: 2px;
        }
        QScrollArea { background: transparent; border: none; }
        QScrollBar:vertical {
            width: 6px;
            background: transparent;
        }
        QScrollBar::handle:vertical {
            background: #174b60;
            border-radius: 3px;
            min-height: 35px;
        }
        #bubbleNova, #bubbleUser {
            border-radius: 15px;
            padding: 1px;
        }
        #bubbleNova {
            background: #07131c;
            border: 1px solid #123d50;
        }
        #bubbleUser {
            background: #081a22;
            border: 1px solid #145269;
        }
        #bubbleWho {
            color: #54e8ff;
            font-size: 8px;
            font-weight: 800;
            letter-spacing: 1.8px;
        }
        #bubbleBody {
            color: #d6f6ff;
            font-size: 12px;
            line-height: 1.45;
        }
        QLineEdit {
            background: #06131c;
            border: 1px solid #155066;
            border-radius: 14px;
            padding: 12px 15px;
            color: #e7fdff;
            font-size: 13px;
        }
        QLineEdit:focus { border: 1px solid #20dfff; }
        QPushButton {
            background: #081b25;
            border: 1px solid #164d62;
            border-radius: 10px;
            padding: 9px 11px;
            color: #8feeff;
            font-weight: 750;
            font-size: 9px;
            letter-spacing: 1px;
        }
        QPushButton:hover {
            background: #0b2a39;
            border-color: #26dfff;
        }
        QPushButton:pressed { background: #0c3b4e; }
        #listenButton { min-width: 92px; }
        #sendButton {
            min-width: 92px;
            background: #0b3141;
            border-color: #1f8baa;
            color: #bafaff;
        }
        #attachButton {
            min-width: 36px;
            font-size: 13px;
            padding: 8px 10px;
        }
        #sendButton:hover { background: #0e465b; }
        """

    def add_message(self, who, text):
        bubble = ChatBubble(who, text)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.chat.addWidget(bubble)
        QTimer.singleShot(
            20,
            lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            ),
        )

    def run_quick(self, command):
        self.input.setText(command)
        self.send()

    def write_log(self, text):
        clean = str(text).replace("[NOVA]", "").strip()
        if clean:
            self.activity.setText(clean[:70].upper())

    def set_state(self, state):
        self.sphere.set_state(state)
        self.write_log(state)
        state = str(state).upper()
        if state == "READY":
            self.status.setText("● READY")
        elif state == "THINKING":
            self.status.setText("● THINKING")
        elif state == "LISTENING":
            self.status.setText("● LISTENING")
        elif state == "SPEAKING":
            self.status.setText("● SPEAKING")
        else:
            self.status.setText("● " + state[:16])

    def on_state(self, state):
        self.set_state(state)

    def set_expression_from_text(self, text):
        """Choose a lightweight visual emotion from NOVA's response text."""
        t = str(text).lower()
        if any(x in t for x in ("error", "failed", "couldn't", "cannot", "unable", "warning")):
            expr = "ALERT"
        elif any(x in t for x in ("sorry", "sad", "unfortunately")):
            expr = "SAD"
        elif any(x in t for x in ("?", "which", "what", "why", "how")):
            expr = "CURIOUS"
        elif any(x in t for x in ("great", "done", "success", "hello", "hi ", "hey ", "opened", "found")):
            expr = "HAPPY"
        else:
            expr = "NEUTRAL"
        self.sphere.set_expression(expr)

    def set_speaking(self, on):
        self.sphere.set_state(
            "SPEAKING" if on else ("LISTENING" if self.listening else "READY")
        )

    def speak_text(self, text):
        if self._tts:
            threading.Thread(
                target=self._tts.speak,
                args=(text,),
                daemon=True,
            ).start()

    def stop_speaking(self):
        if self._tts:
            self._tts.stop()

    def send(self):
        text = self.input.text().strip()
        if not text:
            return

        self.input.clear()
        self.add_message("YOU", text)
        low = text.lower().strip()

        if low in ("listen", "start listening", "listen now"):
            self.start_listening()
            self.add_message("NOVA", "Listening.")
            return

        if low in ("stop listening", "stop listen", "stop hearing"):
            self.stop_listening()
            self.add_message("NOVA", "Stopped listening.")
            return

        if low in ("stop speaking", "be quiet", "shut up"):
            self.stop_speaking()
            self.add_message("NOVA", "Stopped speaking.")
            return

        if low in ("connect email", "connect my email", "add email", "connect an email"):
            address, ok = QInputDialog.getText(self, "Connect Email", "Email address:")
            if not ok or not address.strip():
                return
            password, ok = QInputDialog.getText(
                self, "Email App Password",
                "Provider app-password (NOT your normal account password):",
                QLineEdit.EchoMode.Password
            )
            if not ok or not password:
                return
            self.add_message("NOVA", f"Connecting {address.strip()} securely…")
            self.set_state("THINKING")
            def email_work():
                try:
                    reply = self.orchestrator._run("email_manager", {
                        "action": "connect",
                        "email": address.strip(),
                        "password": password,
                    })
                except Exception as exc:
                    reply = f"Email connection failed: {exc}"
                self.bus.reply.emit(str(reply), "local")
            Worker(email_work).start()
            return

        self.sphere.set_expression("CURIOUS")
        self.set_state("THINKING")
        provider = self.provider.currentText().lower()
        provider = None if provider == "auto" else provider

        def work():
            try:
                reply, used = self.orchestrator.handle(text, provider)
            except Exception as exc:
                reply, used = f"I couldn't complete that action: {exc}", "error"
            self.bus.reply.emit(str(reply), str(used))

        Worker(work).start()

    def on_reply(self, reply, provider):
        self.add_message("NOVA", reply)
        self.set_expression_from_text(reply)
        self.set_state("READY")
        if provider and provider not in ("local", "error"):
            self.activity.setText(f"{provider.upper()} RESPONSE")
        if provider != "error":
            self.speak_text(reply)

    def select_attachment(self):
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Attach to NOVA Task", "", "All Files (*.*)")
        if file_path:
            self.orchestrator.set_attachment(file_path)
            self.add_message("SYSTEM", f"📎 Attached: {Path(file_path).name}\nPath: {file_path}")

    def toggle_listen(self):
        if self.listening:
            self.stop_listening()
        else:
            self.start_listening()

    def start_listening(self):
        if self.listening:
            return
        self.listening = True
        self.sphere.set_expression("CURIOUS")
        self.listen.setText("■  STOP")
        self.set_state("LISTENING")
        Worker(self._record_once).start()

    def stop_listening(self):
        self.listening = False
        self.listen.setText("◉  LISTEN")
        self.set_state("READY")

    def _record_once(self):
        try:
            import sounddevice as sd
            import soundfile as sf
            import tempfile
            import os
            from openai import OpenAI
            from core import config

            if not config.GROQ_API_KEY:
                raise RuntimeError("Groq API key is not configured for voice input.")

            fs = 16000
            seconds = 7
            audio = sd.rec(
                int(seconds * fs),
                samplerate=fs,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            if not self.listening:
                return

            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            sf.write(path, audio, fs)

            client = OpenAI(
                api_key=config.GROQ_API_KEY,
                base_url=config.GROQ_BASE_URL,
                timeout=30,
            )
            with open(path, "rb") as f:
                tr = client.audio.transcriptions.create(
                    model=config.GROQ_STT_MODEL,
                    file=f,
                )

            try:
                os.unlink(path)
            except Exception:
                pass

            text = getattr(tr, "text", "").strip()
            if text:
                self.bus.voice_text.emit(text)
            else:
                self.stop_listening()
        except Exception as exc:
            self.bus.reply.emit(f"Voice input failed: {exc}", "error")
            self.stop_listening()

    def on_voice_text(self, text):
        self.stop_listening()
        self.input.setText(text)
        self.send()
