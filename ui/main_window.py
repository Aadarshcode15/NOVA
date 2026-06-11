# ui/main_window.py
import os
import datetime
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFileDialog,
    QHBoxLayout, QVBoxLayout, QFrame, QSizePolicy
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt6.QtGui   import QFont, QTextCursor, QColor, QKeyEvent

from ui.styles  import MAIN_STYLESHEET
from ui.widgets import CircularVisualizer, WaveformBar, SystemMonitor
from core.voice import on as voice_on, speak, speak_nova, speak_sora, VoiceState
from core.engine import get_engine, get_assistant, set_engine, set_assistant, Engine
from config.settings import UI_TITLE, UI_SUBTITLE, UI_WIDTH, UI_HEIGHT

class CommandWorker(QObject):
    finished = pyqtSignal()
    def __init__(self, assistant, command):
        super().__init__()
        self._a = assistant; self._c = command
    def run(self):
        from core.command_router import route
        try: route(self._a, self._c)
        except SystemExit: pass
        except Exception as e: print(f"[Worker] {e}")
        self.finished.emit()

class NovaWindow(QMainWindow):
    sig_log        = pyqtSignal(str, str)
    sig_state      = pyqtSignal(str)
    sig_transcript = pyqtSignal(dict)
    sig_response   = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.resize(UI_WIDTH, UI_HEIGHT)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(MAIN_STYLESHEET)
        self._uploaded_file = None
        self._muted = False
        self._threads = []
        self._build_ui()
        self._start_clock()
        self._register_voice_callbacks()
        self.sig_log.connect(self._append_log)
        self.sig_state.connect(self._on_state)
        self.sig_transcript.connect(lambda d: self._append_log(d["who"], d["text"]))
        self.sig_response.connect(lambda d: self._append_log(d["who"], d["text"]))
        self._append_log("sys", f"[ N.O.V.A ONLINE — {UI_SUBTITLE} ]")
        self._append_log("sys", "[ Always listening — speak naturally ]")
        self._append_log("sys", "─" * 50)

    def _build_ui(self):
        central = QWidget(); central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._build_left())
        root.addWidget(self._build_center(), 1)
        root.addWidget(self._build_right())

    # ── LEFT PANEL ───────────────────────────────────────
    def _build_left(self):
        p = QWidget(); p.setObjectName("leftPanel"); p.setFixedWidth(155)
        lay = QVBoxLayout(p); lay.setContentsMargins(10,12,10,12); lay.setSpacing(8)

        self._sec("● SYS MONITOR", lay)
        self._sys_mon = SystemMonitor()
        lay.addWidget(self._sys_mon)
        self._div(lay)

        self._sec("ACTIVE", lay)
        self._asst_lbl = QLabel("● NOVA-M")
        self._asst_lbl.setObjectName("assistantLabel")
        self._asst_lbl.setStyleSheet("color:#00c8ff; font-size:13px; font-weight:bold; letter-spacing:2px;")
        lay.addWidget(self._asst_lbl)

        self._sec("STATE", lay)
        self._state_lbl = QLabel("● STANDBY")
        self._state_lbl.setObjectName("stateLabel")
        self._state_lbl.setStyleSheet("color:#2a4a5e; font-size:11px; font-weight:bold; letter-spacing:2px;")
        lay.addWidget(self._state_lbl)
        self._div(lay)

        self._sec("ENGINE", lay)
        self._btn_gemini = self._eng_btn("GEMINI", Engine.GEMINI)
        self._btn_groq   = self._eng_btn("GROQ",   Engine.GROQ)
        self._btn_ollama = self._eng_btn("OLLAMA",  Engine.OLLAMA)
        lay.addWidget(self._btn_gemini)
        lay.addWidget(self._btn_groq)
        lay.addWidget(self._btn_ollama)
        self._refresh_engine_btns()
        self._div(lay)

        # ── SORA switch button ──
        self._sora_btn = QPushButton("⟳  SWITCH TO SORA")
        self._sora_btn.setFixedHeight(32)
        self._sora_btn.setStyleSheet(
            "QPushButton{background:#c084fc22;border:1px solid #c084fc88;"
            "color:#c084fc;font-size:9px;font-weight:bold;letter-spacing:1px;padding:4px;}"
            "QPushButton:hover{background:#c084fc44;border:1px solid #c084fc;}"
        )
        self._sora_btn.clicked.connect(self._toggle_assistant)
        lay.addWidget(self._sora_btn)
        self._div(lay)

        self._sec("VERSION", lay)
        for label, active in [("AI CORE\nACTIVE", True),("SEC\nCLEARED", True),("V 2 . 0\nREMASTERED", False)]:
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            if active:
                btn.setStyleSheet(
                    "QPushButton{background:#00ff8811;border:1px solid #00ff8855;"
                    "color:#00ff88;font-size:8px;font-weight:bold;letter-spacing:1px;padding:4px;}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton{background:#0a1220;border:1px solid #1a3a50;"
                    "color:#2a4a5e;font-size:8px;font-weight:bold;letter-spacing:1px;padding:4px;}"
                )
            lay.addWidget(btn)

        lay.addStretch()
        hint = QLabel("[F4] Mute    [F11] Full")
        hint.setStyleSheet("color:#1a3a50;font-size:8px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(hint)
        return p

    # ── CENTER PANEL ─────────────────────────────────────
    def _build_center(self):
        p = QWidget(); p.setObjectName("centerPanel")
        lay = QVBoxLayout(p); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # Top bar
        top = QWidget(); top.setObjectName("topBar"); top.setFixedHeight(58)
        tl  = QHBoxLayout(top); tl.setContentsMargins(16,0,16,0)
        sp  = QWidget(); sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        tc = QVBoxLayout(); tc.setSpacing(2)
        self._title = QLabel(UI_TITLE)
        self._title.setObjectName("titleLabel")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub = QLabel(UI_SUBTITLE)
        self._sub.setObjectName("subtitleLabel")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tc.addWidget(self._title); tc.addWidget(self._sub)

        rc = QVBoxLayout(); rc.setSpacing(1)
        rc.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._clock = QLabel("00:00:00")
        self._clock.setObjectName("clockLabel")
        self._clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._date  = QLabel("Mon 01 Jun 2026")
        self._date.setObjectName("dateLabel")
        self._date.setAlignment(Qt.AlignmentFlag.AlignRight)
        rc.addWidget(self._clock); rc.addWidget(self._date)

        tl.addWidget(sp); tl.addLayout(tc); tl.addStretch(); tl.addLayout(rc)
        lay.addWidget(top)

        # Visualizer
        self._vis = CircularVisualizer()
        lay.addWidget(self._vis, 1, Qt.AlignmentFlag.AlignCenter)

        # State label
        self._cstate = QLabel("● STANDBY")
        self._cstate.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cstate.setStyleSheet("color:#2a4a5e;letter-spacing:4px;font-size:12px;font-weight:bold;font-family:'Courier New';")
        lay.addWidget(self._cstate)

        # Waveform
        self._wave = WaveformBar()
        lay.addWidget(self._wave)

        # Bottom bar
        bot = QWidget(); bot.setObjectName("bottomBar"); bot.setFixedHeight(30)
        bl  = QHBoxLayout(bot); bl.setContentsMargins(16,0,16,0)
        fl  = QLabel("Aadarsh Labs   ·   v2   ·   Remastered")
        fl.setStyleSheet("color:#1a3a50;font-size:8px;letter-spacing:2px;")
        fl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(fl)
        lay.addWidget(bot)
        return p

    # ── RIGHT PANEL ──────────────────────────────────────
    def _build_right(self):
        p = QWidget(); p.setObjectName("rightPanel"); p.setFixedWidth(320)
        lay = QVBoxLayout(p); lay.setContentsMargins(12,12,12,12); lay.setSpacing(8)

        self._sec("▶ ACTIVITY LOG", lay)
        self._log = QTextEdit()
        self._log.setObjectName("logWidget")
        self._log.setReadOnly(True)
        self._log.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(self._log, 2)
        self._div(lay)

        self._sec("▶ FILE UPLOAD", lay)
        self._upload_btn = QPushButton("⬆\n\nDrop file here  or  Click to Browse\n· Images · Video · Audio · PDF · Docs · Code ·")
        self._upload_btn.setObjectName("uploadButton")
        self._upload_btn.setFixedHeight(88)
        self._upload_btn.clicked.connect(self._on_upload)
        lay.addWidget(self._upload_btn)
        self._upload_lbl = QLabel("No file loaded — drop or click above to upload")
        self._upload_lbl.setStyleSheet("color:#2a4a5e;font-size:9px;letter-spacing:1px;")
        self._upload_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._upload_lbl)
        self._div(lay)

        self._sec("▶ COMMAND INPUT", lay)
        row = QHBoxLayout(); row.setSpacing(6)
        self._cmd = QLineEdit()
        self._cmd.setObjectName("commandInput")
        self._cmd.setPlaceholderText("Type a command or question...")
        self._cmd.returnPressed.connect(self._on_send)
        row.addWidget(self._cmd)
        sb = QPushButton("▶"); sb.setObjectName("sendButton")
        sb.setFixedWidth(34); sb.clicked.connect(self._on_send)
        row.addWidget(sb)
        lay.addLayout(row)

        # Mic + fullscreen
        br = QHBoxLayout(); br.setSpacing(6)
        self._mic_btn = QPushButton("🎤  MICROPHONE ACTIVE")
        self._mic_btn.setFixedHeight(34)
        self._mic_btn.setStyleSheet(
            "QPushButton{background:#00ff8822;border:1px solid #00ff8866;"
            "color:#00ff88;font-size:10px;font-weight:bold;padding:4px;}"
            "QPushButton:hover{background:#00ff8844;border:1px solid #00ff88;}"
        )
        self._mic_btn.clicked.connect(self._on_mute)
        br.addWidget(self._mic_btn)

        fs = QPushButton("⛶  FULLSCREEN  [F11]")
        fs.setFixedHeight(34)
        fs.setStyleSheet(
            "QPushButton{background:transparent;border:1px solid #1a3a50;"
            "color:#2a4a5e;font-size:9px;font-weight:bold;padding:4px;}"
            "QPushButton:hover{border:1px solid #00c8ff55;color:#00c8ff;}"
        )
        fs.clicked.connect(self._toggle_fs)
        br.addWidget(fs)
        lay.addLayout(br)
        return p

    # ── Helpers ──────────────────────────────────────────
    def _sec(self, text, layout):
        l = QLabel(text)
        l.setStyleSheet("color:#2a4a5e;font-size:8px;letter-spacing:3px;padding:2px 0px;font-family:'Courier New';")
        layout.addWidget(l)

    def _div(self, layout):
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background:#1a3a50;max-height:1px;border:none;")
        layout.addWidget(f)

    def _eng_btn(self, label, engine_val):
        btn = QPushButton(f"● {label}")
        btn.setFixedHeight(26)
        btn.clicked.connect(lambda _, e=engine_val: self._on_engine(e))
        return btn

    def _refresh_engine_btns(self):
        eng = get_engine()
        cfg = {
            Engine.GEMINI: ("#4285f4", self._btn_gemini),
            Engine.GROQ:   ("#ff6b35", self._btn_groq),
            Engine.OLLAMA: ("#00ff88", self._btn_ollama),
        }
        for e, (c, btn) in cfg.items():
            if e == eng:
                btn.setStyleSheet(
                    f"QPushButton{{background:{c}15;border:1px solid {c}99;"
                    f"color:{c};font-size:9px;font-weight:bold;padding:3px 8px;letter-spacing:1px;}}"
                    f"QPushButton:hover{{background:{c}30;}}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton{background:transparent;border:1px solid #1a3a50;"
                    "color:#2a4a5e;font-size:9px;font-weight:bold;padding:3px 8px;letter-spacing:1px;}"
                    "QPushButton:hover{border:1px solid #00c8ff55;color:#00c8ff;}"
                )

    def _register_voice_callbacks(self):
        voice_on("state_change", lambda s: self.sig_state.emit(s))
        voice_on("transcript",   lambda d: self.sig_transcript.emit(d))
        voice_on("response",     lambda d: self.sig_response.emit(d))

    def _start_clock(self):
        t = QTimer(self); t.timeout.connect(self._tick_clock); t.start(1000)
        self._tick_clock()

    def _tick_clock(self):
        n = datetime.datetime.now()
        self._clock.setText(n.strftime("%H:%M:%S"))
        self._date.setText(n.strftime("%a %d %b %Y"))

    # ── Log ──────────────────────────────────────────────
    def _append_log(self, who, text):
        colors   = {"user":"#f0a500","nova":"#00c8ff","sora":"#c084fc","sys":"#2a4a5e"}
        prefixes = {"user":"You    ▶","nova":"NOVA   ▶","sora":"SORA   ▶","sys":""}
        color    = colors.get(who, "#a0cfe0")
        prefix   = prefixes.get(who, "")
        msg      = f"{prefix}  {text}" if prefix else text
        cur = self._log.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = cur.charFormat(); fmt.setForeground(QColor(color))
        cur.setCharFormat(fmt); cur.insertText(msg + "\n")
        self._log.setTextCursor(cur); self._log.ensureCursorVisible()

    # ── State ─────────────────────────────────────────────
    def _on_state(self, state):
        cfg = {
            VoiceState.LISTENING: ("● LISTENING", "#00c8ff"),
            VoiceState.SPEAKING:  ("● SPEAKING",  "#00ff88"),
            VoiceState.THINKING:  ("● THINKING",  "#f0a500"),
            VoiceState.IDLE:      ("● STANDBY",   "#2a4a5e"),
        }
        lbl, col = cfg.get(state, ("● STANDBY","#2a4a5e"))
        ss = f"color:{col};font-size:11px;font-weight:bold;letter-spacing:2px;font-family:'Courier New';"
        self._state_lbl.setText(lbl); self._state_lbl.setStyleSheet(ss)
        self._cstate.setText(lbl)
        self._cstate.setStyleSheet(f"color:{col};letter-spacing:4px;font-size:12px;font-weight:bold;font-family:'Courier New';")
        asst = get_assistant()
        self._vis.set_state(state);  self._vis.set_assistant(asst)
        self._wave.set_state(state); self._wave.set_assistant(asst)
        # Update assistant label
        al  = "● NOVA-M" if asst == "nova" else "● SORA-F"
        ac  = "#00c8ff"  if asst == "nova" else "#c084fc"
        self._asst_lbl.setText(al)
        self._asst_lbl.setStyleSheet(f"color:{ac};font-size:13px;font-weight:bold;letter-spacing:2px;font-family:'Courier New';")
        # Update sora button
        if asst == "nova":
            self._sora_btn.setText("⟳  SWITCH TO SORA")
            self._sora_btn.setStyleSheet(
                "QPushButton{background:#c084fc22;border:1px solid #c084fc88;"
                "color:#c084fc;font-size:9px;font-weight:bold;letter-spacing:1px;padding:4px;}"
                "QPushButton:hover{background:#c084fc44;border:1px solid #c084fc;}"
            )
        else:
            self._sora_btn.setText("⟳  SWITCH TO NOVA")
            self._sora_btn.setStyleSheet(
                "QPushButton{background:#00c8ff22;border:1px solid #00c8ff88;"
                "color:#00c8ff;font-size:9px;font-weight:bold;letter-spacing:1px;padding:4px;}"
                "QPushButton:hover{background:#00c8ff44;border:1px solid #00c8ff;}"
            )

    # ── Engine ────────────────────────────────────────────
    def _on_engine(self, engine):
        set_engine(engine)
        self._refresh_engine_btns()
        names = {Engine.GEMINI:"GEMINI", Engine.GROQ:"GROQ", Engine.OLLAMA:"OLLAMA"}
        self._append_log("sys", f"[ Engine → {names.get(engine, engine)} ]")

    # ── Toggle assistant ──────────────────────────────────
    def _toggle_assistant(self):
        current = get_assistant()
        if current == "nova":
            set_assistant("sora")
            self._append_log("sys", "[ Switched to SORA ]")
            speak_sora("SORA online.")
        else:
            set_assistant("nova")
            self._append_log("sys", "[ Switched to NOVA ]")
            speak_nova("NOVA online.")
        self._on_state(VoiceState.IDLE)

    # ── Send text ─────────────────────────────────────────
    def _on_send(self):
        text = self._cmd.text().strip()
        if not text: return
        self._cmd.clear()
        self._append_log("user", text)
        if self._uploaded_file:
            text = f"[File: {Path(self._uploaded_file).name}] {text}"
        asst   = get_assistant()
        worker = CommandWorker(asst, text)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start(); self._threads.append(thread)

    # ── Upload ────────────────────────────────────────────
    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(self, "Upload File", str(Path.home()),
            "All Files (*.*)")
        if path:
            self._uploaded_file = path
            fname = Path(path).name
            self._upload_lbl.setText(f"✓ {fname}")
            self._upload_lbl.setStyleSheet("color:#00c8ff;font-size:9px;")
            self._append_log("sys", f"[ File loaded: {fname} ]")

    # ── Mute ──────────────────────────────────────────────
    def _on_mute(self):
        from core.voice import stop_audio_loop, audio_loop
        import threading
        self._muted = not self._muted
        if self._muted:
            stop_audio_loop()
            self._mic_btn.setText("🔇  MICROPHONE MUTED")
            self._mic_btn.setStyleSheet(
                "QPushButton{background:#ff335522;border:1px solid #ff335566;"
                "color:#ff3355;font-size:10px;font-weight:bold;padding:4px;}"
            )
            self._append_log("sys","[ Microphone muted ]")
        else:
            threading.Thread(target=audio_loop, daemon=True).start()
            self._mic_btn.setText("🎤  MICROPHONE ACTIVE")
            self._mic_btn.setStyleSheet(
                "QPushButton{background:#00ff8822;border:1px solid #00ff8866;"
                "color:#00ff88;font-size:10px;font-weight:bold;padding:4px;}"
                "QPushButton:hover{background:#00ff8844;}"
            )
            self._append_log("sys","[ Microphone active ]")

    # ── Fullscreen ────────────────────────────────────────
    def _toggle_fs(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()
        
    def closeEvent(self, event) -> None:
        """Minimise to tray instead of quitting when window is closed."""
        if hasattr(self, "_tray") and self._tray:
            event.ignore()
            self.hide()
            self._tray.notify(
                "N.O.V.A",
                "Running in the background.\n"
                "Double-click the tray icon to restore."
            )
        else:
            event.accept()


    # ── Keys ──────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11: self._toggle_fs()
        elif event.key() == Qt.Key.Key_F4: self._on_mute()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen(): self.showNormal()
        else: super().keyPressEvent(event)

    # ── Drag & Drop ───────────────────────────────────────
    def showEvent(self, e):
        super().showEvent(e); self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            path  = urls[0].toLocalFile()
            self._uploaded_file = path
            fname = Path(path).name
            self._upload_lbl.setText(f"✓ {fname}")
            self._upload_lbl.setStyleSheet("color:#00c8ff;font-size:9px;")
            self._append_log("sys", f"[ File loaded: {fname} ]")
