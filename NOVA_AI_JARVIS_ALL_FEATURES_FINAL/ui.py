from __future__ import annotations

import math
import random
import threading

from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush, QRadialGradient, QFont, QLinearGradient
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


class Sphere(QWidget):
    def __init__(self):
        super().__init__()
        self.phase = 0.0
        self.amp = 0.0
        self.state = "READY"
        self.setMinimumSize(390, 390)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def set_state(self, state):
        self.state = state.upper()
        self.update()

    def set_amp(self, amp):
        self.amp = max(0.0, min(1.0, float(amp)))
        self.update()

    def tick(self):
        self.phase = (self.phase + 0.018 + 0.028 * self.amp) % math.tau
        self.amp *= 0.94
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2 - 12
        r = min(w, h) * 0.265

        p.fillRect(self.rect(), QColor("#03070c"))

        random.seed(27)
        for _ in range(115):
            x = random.random() * w
            y = random.random() * h
            alpha = int(16 + 42 * random.random())
            p.setPen(QPen(QColor(65, 205, 245, alpha), 1))
            p.drawPoint(int(x), int(y))

        # Outer aura.
        for mul, alpha in ((2.5, 12), (2.05, 17), (1.65, 25), (1.35, 38)):
            rr = r * mul * (1 + 0.025 * math.sin(self.phase * 1.6))
            g = QRadialGradient(cx, cy, rr)
            g.setColorAt(0, QColor(0, 218, 255, alpha))
            g.setColorAt(0.55, QColor(0, 115, 255, alpha // 2))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # Orb body.
        rr = r * (1 + 0.035 * math.sin(self.phase * 2.0) + 0.065 * self.amp)
        g = QRadialGradient(cx - r * 0.3, cy - r * 0.35, rr * 1.35)
        g.setColorAt(0, QColor("#f2ffff"))
        g.setColorAt(0.08, QColor("#9df9ff"))
        g.setColorAt(0.33, QColor("#20dcff"))
        g.setColorAt(0.67, QColor("#087bc9"))
        g.setColorAt(1, QColor("#00142b"))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(91, 240, 255, 185), 1.3))
        p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # Animated energy rings.
        for k in range(8):
            off = self.phase * (1 if k % 2 else -1) + k * 0.74
            rx = rr * (0.28 + 0.72 * abs(math.sin(off)))
            ry = rr * (0.07 + 0.14 * abs(math.cos(off)))
            alpha = 55 + int(75 * self.amp)
            p.setPen(QPen(QColor(145, 247, 255, alpha), 1.1))
            p.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))

        # Core.
        cr = r * 0.235 * (1 + 0.08 * self.amp)
        cg = QRadialGradient(cx - cr * 0.35, cy - cr * 0.4, cr)
        cg.setColorAt(0, QColor("#ffffff"))
        cg.setColorAt(0.25, QColor("#c6ffff"))
        cg.setColorAt(0.7, QColor("#00d9ff"))
        cg.setColorAt(1, QColor(0, 55, 105, 0))
        p.setBrush(QBrush(cg))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx - cr, cy - cr, cr * 2, cr * 2))

        p.setPen(QColor("#75efff"))
        font = QFont("Segoe UI", 10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.2)
        p.setFont(font)
        p.drawText(
            QRectF(cx - 120, cy + r * 1.48, 240, 30),
            Qt.AlignmentFlag.AlignCenter,
            self.state,
        )
        p.end()


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

        body = QLabel(str(text))
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setObjectName("bubbleBody")
        layout.addWidget(body)


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

        self.sphere = Sphere()
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

        self.set_state("THINKING")
        provider = self.provider.currentText().lower()
        provider = None if provider == "auto" else provider

        def work():
            try:
                direct = self.orchestrator._direct(text)
                if direct is not None:
                    reply, used = direct, "local"
                else:
                    reply, used = self.orchestrator.handle(text, provider)
            except Exception as exc:
                reply, used = f"I couldn't complete that action: {exc}", "error"
            self.bus.reply.emit(str(reply), str(used))

        Worker(work).start()

    def on_reply(self, reply, provider):
        self.add_message("NOVA", reply)
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
