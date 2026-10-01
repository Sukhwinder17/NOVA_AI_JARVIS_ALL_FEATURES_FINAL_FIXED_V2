from __future__ import annotations

import math
import random
import threading

from memory.conversation_history import load_history

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
        cx, cy = w / 2, h / 2 - 18
        base = min(w, h) * 0.30
        pulse = 1.0 + 0.035 * math.sin(self.phase * 2.0) + 0.05 * self.amp

        p.fillRect(self.rect(), QColor("#020308"))

        # Deep-space star field.
        random.seed(42)
        for _ in range(180):
            x = random.random() * w
            y = random.random() * h
            a = int(18 + 45 * random.random())
            p.setPen(QPen(QColor(100, 190, 255, a), 1))
            p.drawPoint(int(x), int(y))

        # Gravitational aura.
        for mul, alpha in ((2.25, 10), (1.85, 15), (1.48, 22), (1.18, 34)):
            rr = base * mul * pulse
            g = QRadialGradient(cx, cy, rr)
            g.setColorAt(0.0, QColor(0, 220, 255, alpha))
            g.setColorAt(0.48, QColor(65, 80, 255, alpha // 2))
            g.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # Rotating accretion disk — flattened, luminous, black-hole-like.
        for k in range(18):
            a = self.phase * (1.0 if k % 2 else -0.72) + k * 0.34
            rx = base * (0.98 + 0.12 * math.sin(a * 1.7))
            ry = base * (0.16 + 0.045 * math.sin(a * 2.2))
            p.save()
            p.translate(cx, cy)
            p.rotate(math.degrees(a))
            p.translate(-cx, -cy)
            pen = QPen(QColor(40, 220, 255, 24 + int(55 * self.amp)), 1.2 + (k % 3) * 0.35)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))
            p.restore()

        # Bright event horizon ring.
        ring_r = base * (0.72 + 0.025 * math.sin(self.phase * 3.0))
        for width, alpha in ((10, 28), (6, 60), (2, 180)):
            pen = QPen(QColor(75, 235, 255, alpha), width)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - ring_r, cy - ring_r * 0.42, ring_r * 2, ring_r * 0.84))

        # The actual black hole.
        hole_r = base * 0.48 * (1.0 + 0.025 * self.amp)
        hg = QRadialGradient(cx - hole_r * 0.15, cy - hole_r * 0.12, hole_r)
        hg.setColorAt(0.0, QColor("#000000"))
        hg.setColorAt(0.72, QColor("#000000"))
        hg.setColorAt(0.90, QColor(1, 7, 13, 245))
        hg.setColorAt(1.0, QColor(0, 120, 170, 80))
        p.setBrush(QBrush(hg))
        p.setPen(QPen(QColor(100, 245, 255, 120), 1))
        p.drawEllipse(QRectF(cx - hole_r, cy - hole_r, hole_r * 2, hole_r * 2))

        # Orbiting energy particles.
        for k in range(14):
            a = self.phase * (1.3 if k % 2 else -0.9) + k * (math.tau / 14)
            rr = base * (0.78 + 0.16 * math.sin(self.phase + k))
            x = cx + math.cos(a) * rr
            y = cy + math.sin(a) * rr * 0.30
            dot = 2.0 + 2.5 * self.amp
            p.setBrush(QBrush(QColor(120, 245, 255, 120 + int(100 * self.amp))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(x-dot, y-dot, dot*2, dot*2))

        p.setPen(QColor("#75efff"))
        font = QFont("Segoe UI", 10)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.2)
        p.setFont(font)
        p.drawText(QRectF(cx - 120, cy + base * 1.38, 240, 30), Qt.AlignmentFlag.AlignCenter, self.state)
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
        self.resize(1500, 940)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(self.css())

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(22, 18, 22, 18)
        main.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(14)
        hello = QVBoxLayout()
        hello.setSpacing(0)
        greeting = QLabel("HELLO,")
        greeting.setObjectName("greeting")
        hello.addWidget(greeting)
        name = QLabel("SUKHWINDER")
        name.setObjectName("heroName")
        hello.addWidget(name)
        sub = QLabel("PERSONAL AI • LOCAL CONTROL • LIVE ACTIONS")
        sub.setObjectName("brandSub")
        hello.addWidget(sub)
        header.addLayout(hello)
        header.addStretch()

        brand = QLabel("N O V A")
        brand.setObjectName("brand")
        header.addWidget(brand)

        self.status = QLabel("● READY")
        self.status.setObjectName("status")
        header.addWidget(self.status)

        self.provider = QComboBox()
        self.provider.addItems(["AUTO", "GROQ", "GEMINI", "XKIRO"])
        self.provider.setToolTip("AI provider used for conversation and tool decisions")
        self.provider.setFixedWidth(118)
        header.addWidget(self.provider)
        main.addLayout(header)

        stage = QHBoxLayout()
        stage.setSpacing(14)
        main.addLayout(stage, 1)

        left = QFrame()
        left.setObjectName("hudPanel")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 18, 16, 16)
        ll.setSpacing(9)

        leftTitle = QLabel("NOVA")
        leftTitle.setObjectName("sideTitle")
        ll.addWidget(leftTitle)
        leftSub = QLabel("YOUR AI ASSISTANT")
        leftSub.setObjectName("sideSub")
        ll.addWidget(leftSub)

        def hud_button(label, icon, command):
            b = QPushButton(f"{icon}   {label}   ›")
            b.setObjectName("hudButton")
            b.clicked.connect(lambda checked=False, c=command: self.run_quick(c))
            ll.addWidget(b)

        hud_button("SEARCH FILES", "⌕", "find my files")
        hud_button("OPEN APPS", "▦", "show my apps")
        hud_button("WEB SEARCH", "◎", "open google")
        hud_button("ANALYZE DATA", "▥", "open datalens")
        hud_button("CREATE / GENERATE", "✦", "help me create something")
        hud_button("SYSTEM CONTROL", "⚙", "check nova features")

        ll.addStretch()
        mic = QLabel("◉  〰〰〰〰〰〰  ◉")
        mic.setObjectName("wave")
        mic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(mic)
        listenText = QLabel("VOICE READY")
        listenText.setObjectName("sideSub")
        listenText.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(listenText)
        stage.addWidget(left, 22)

        center = QFrame()
        center.setObjectName("corePanel")
        cl = QVBoxLayout(center)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(2)

        coreTop = QLabel("NOVA CORE")
        coreTop.setObjectName("coreTitle")
        coreTop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(coreTop)
        coreSub = QLabel("SMARTER • FASTER • ALWAYS WITH YOU")
        coreSub.setObjectName("coreSub")
        coreSub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(coreSub)

        self.sphere = Sphere()
        cl.addWidget(self.sphere, 1)

        self.activity = QLabel("SYSTEM READY")
        self.activity.setObjectName("activity")
        self.activity.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(self.activity)
        stage.addWidget(center, 56)

        right = QFrame()
        right.setObjectName("hudPanel")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(16, 18, 16, 16)
        rl.setSpacing(10)

        sysTitle = QLabel("SYSTEM STATUS")
        sysTitle.setObjectName("sideTitle")
        rl.addWidget(sysTitle)

        stats = QHBoxLayout()
        for label, value in (("CPU", "—"), ("RAM", "—"), ("GPU", "—")):
            box = QFrame()
            box.setObjectName("statBox")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(7, 8, 7, 8)
            bl.setSpacing(1)
            v = QLabel(value)
            v.setObjectName("statValue")
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bl.addWidget(v)
            t = QLabel(label)
            t.setObjectName("statLabel")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bl.addWidget(t)
            stats.addWidget(box)
        rl.addLayout(stats)

        qa = QLabel("QUICK ACTIONS")
        qa.setObjectName("sideTitle")
        rl.addWidget(qa)
        for label, icon, command in [
            ("Find my file", "⌕", "find my files"),
            ("Summarize this", "≡", "summarize this"),
            ("Create a report", "▤", "create a report"),
            ("Open YouTube", "▶", "open youtube"),
            ("Take a screenshot", "▣", "take a screenshot"),
            ("DataLens", "◈", "open datalens"),
        ]:
            b = QPushButton(f"{icon}   {label}   ›")
            b.setObjectName("actionButton")
            b.clicked.connect(lambda checked=False, c=command: self.run_quick(c))
            rl.addWidget(b)

        rl.addStretch()
        stage.addWidget(right, 22)

        chatDock = QFrame()
        chatDock.setObjectName("chatDock")
        dl = QVBoxLayout(chatDock)
        dl.setContentsMargins(14, 10, 14, 10)
        dl.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("LIVE COMMAND CHANNEL")
        title.setObjectName("section")
        top.addWidget(title)
        top.addStretch()
        hint = QLabel("FILE RESULTS APPEAR HERE • NO EXTRA EVERYTHING WINDOW")
        hint.setObjectName("liveLabel")
        top.addWidget(hint)
        dl.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        self.chat = QVBoxLayout(holder)
        self.chat.setContentsMargins(2, 2, 4, 2)
        self.chat.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat.setSpacing(8)
        self.scroll.setWidget(holder)
        dl.addWidget(self.scroll, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Talk to NOVA — e.g.  find my gradient descent files  •  open Blender  •  send hi")
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
        dl.addLayout(row)

        self.quick = QLabel("Say “find my gradient descent files” → NOVA instantly shows the matching file list here. Then say “open 2”.")
        self.quick.setObjectName("quick")
        dl.addWidget(self.quick)
        main.addWidget(chatDock, 0)

        previous = load_history(24)
        if previous:
            for item in previous:
                self.add_message("YOU" if item["role"] == "user" else "NOVA", item["content"])
        else:
            self.add_message("NOVA", "Hello. I’m NOVA. Tell me what you want done — find a file, open an app, control the browser, send a message, analyze your screen, or just chat.")

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
            background: #02050a;
            color: #d9f8ff;
            font-family: "Segoe UI";
        }
        #greeting { color: #d7f8ff; font-size: 17px; font-weight: 500; letter-spacing: 1px; }
        #heroName { color: #e8fdff; font-size: 25px; font-weight: 800; letter-spacing: 1px; }
        #brandSub { color: #4c879c; font-size: 8px; letter-spacing: 1.7px; margin-top: 3px; }
        #brand { color: #c9faff; font-size: 29px; font-weight: 700; letter-spacing: 8px; padding: 4px 18px; }
        #status {
            color: #61ffc4; font-size: 10px; font-weight: 800; letter-spacing: 1px;
            padding: 8px 12px; border: 1px solid #164f4a; border-radius: 12px; background: #061714;
        }
        QComboBox {
            background: #07131c; border: 1px solid #1b5368; border-radius: 10px;
            padding: 8px 10px; color: #aaf5ff; font-size: 10px; font-weight: 700;
        }
        QComboBox:hover { border-color: #27dfff; }
        #hudPanel, #corePanel, #chatDock {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #06101a, stop:0.52 #040a12, stop:1 #07141d);
            border: 1px solid #12394d; border-radius: 22px;
        }
        #corePanel { border-color: #18506a; }
        #sideTitle { color: #c9f7ff; font-size: 10px; font-weight: 800; letter-spacing: 1.7px; }
        #sideSub { color: #4b8295; font-size: 8px; letter-spacing: 1.6px; }
        #coreTitle { color: #72ecff; font-size: 11px; font-weight: 800; letter-spacing: 3px; margin-top: 2px; }
        #coreSub { color: #3c7287; font-size: 7px; letter-spacing: 2px; }
        #activity { color: #67ecff; font-size: 9px; letter-spacing: 2px; font-weight: 800; }
        #wave { color: #55cfff; font-size: 18px; padding: 9px; border-top: 1px solid #123a4c; }
        #hudButton, #actionButton {
            text-align: left; background: #07131c; border: 1px solid #143f54; border-radius: 13px;
            padding: 11px 10px; color: #b9efff; font-size: 9px; font-weight: 700;
        }
        #hudButton:hover, #actionButton:hover { background: #0b2535; border-color: #27dfff; color: #eaffff; }
        #statBox { background: #06121c; border: 1px solid #123f54; border-radius: 14px; }
        #statValue { color: #64eaff; font-size: 15px; font-weight: 800; }
        #statLabel { color: #4a8192; font-size: 7px; letter-spacing: 1px; }
        #section { color: #6deaff; font-size: 10px; font-weight: 800; letter-spacing: 2px; }
        #liveLabel {
            color: #3e8296; font-size: 7px; letter-spacing: 1px; padding: 5px 8px;
            border: 1px solid #123d4e; border-radius: 8px;
        }
        #quick { color: #416f80; font-size: 8px; }
        QScrollArea { background: transparent; border: none; }
        QScrollBar:vertical { width: 5px; background: transparent; }
        QScrollBar::handle:vertical { background: #174b60; border-radius: 3px; min-height: 30px; }
        #bubbleNova, #bubbleUser, #fileResults { border-radius: 13px; padding: 1px; }
        #bubbleNova { background: #07131c; border: 1px solid #123d50; }
        #bubbleUser { background: #081a22; border: 1px solid #145269; }
        #bubbleWho { color: #54e8ff; font-size: 7px; font-weight: 800; letter-spacing: 1.8px; }
        #bubbleBody { color: #d6f6ff; font-size: 11px; line-height: 1.4; }
        #fileResults { background: #07151e; border: 1px solid #176078; }
        #fileHeader { color: #70ecff; font-size: 9px; font-weight: 800; letter-spacing: 1.5px; }
        #fileQuery { color: #4f8ca0; font-size: 8px; }
        #fileRow {
            background: #07131c; border: 1px solid #113b4c; border-radius: 9px; color: #bcefff;
            text-align: left; padding: 8px 10px; font-size: 9px;
        }
        #fileRow:hover { background: #0b2938; border-color: #27dfff; }
        QLineEdit {
            background: #06131c; border: 1px solid #155066; border-radius: 14px;
            padding: 12px 15px; color: #e7fdff; font-size: 12px;
        }
        QLineEdit:focus { border: 1px solid #20dfff; }
        QPushButton {
            background: #081b25; border: 1px solid #164d62; border-radius: 10px;
            padding: 9px 11px; color: #8feeff; font-weight: 750; font-size: 9px; letter-spacing: 1px;
        }
        QPushButton:hover { background: #0b2a39; border-color: #26dfff; }
        QPushButton:pressed { background: #0c3b4e; }
        #listenButton { min-width: 92px; }
        #sendButton { min-width: 92px; background: #0b3141; border-color: #1f8baa; color: #bafaff; }
        #attachButton { min-width: 36px; font-size: 13px; padding: 8px 10px; }
        #sendButton:hover { background: #0e465b; }
        """
    
    def add_file_results(self, reply):
        import re
        lines = str(reply).splitlines()
        matches = []
        query = ""
        for line in lines:
            m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
            if m:
                matches.append((int(m.group(1)), m.group(2).strip()))
            elif line.lower().startswith("found ") and " for: " in line.lower():
                query = line.split(" for: ", 1)[-1].strip()

        if not matches:
            self.add_message("NOVA", reply)
            return

        card = QFrame()
        card.setObjectName("fileResults")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(7)

        header = QLabel(f"⌕  FILE SEARCH  •  {len(matches)} RESULTS")
        header.setObjectName("fileHeader")
        outer.addWidget(header)

        if query:
            ql = QLabel(f"Search: {query}")
            ql.setObjectName("fileQuery")
            outer.addWidget(ql)

        for number, path in matches:
            label = path if len(path) <= 125 else "…" + path[-124:]
            b = QPushButton(f"{number:02d}   {label}")
            b.setObjectName("fileRow")
            b.setToolTip(path)
            b.clicked.connect(lambda checked=False, n=number: self.open_file_result(n))
            outer.addWidget(b)

        footer = QLabel("Click a result to open it  •  or say “open 2”")
        footer.setObjectName("fileQuery")
        outer.addWidget(footer)

        self.chat.addWidget(card)
        QTimer.singleShot(20, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))

    def open_file_result(self, number):
        self.input.setText(f"open {number}")
        self.send()

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
                reply, used = self.orchestrator.handle(text, provider)
            except Exception as exc:
                reply, used = f"I couldn't complete that action: {exc}", "error"
            self.bus.reply.emit(str(reply), str(used))

        Worker(work).start()

    def on_reply(self, reply, provider):
        text = str(reply)
        if "Found " in text and any(line.lstrip()[:2].isdigit() and ". " in line[:8] for line in text.splitlines()):
            self.add_file_results(text)
        else:
            self.add_message("NOVA", text)
        self.set_state("READY")
        if provider and provider not in ("local", "error"):
            self.activity.setText(f"{provider.upper()} RESPONSE")
        if provider != "error":
            self.speak_text(text)

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
