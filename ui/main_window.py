# ui/main_window.py
import datetime
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton,
    QLineEdit, QFileDialog, QScrollArea,
    QHBoxLayout, QVBoxLayout, QFrame
)
from PyQt6.QtCore  import Qt, QTimer, pyqtSignal

from ui.styles  import MAIN_STYLESHEET
from ui.widgets import CircularVisualizer, WaveformBar, SystemMonitor, LogEntry
from core.voice import on as voice_on, speak, speak_nova, speak_sora, VoiceState
from core.engine import get_engine, get_assistant, set_engine, set_assistant, Engine
from config.settings import UI_TITLE, UI_SUBTITLE, UI_WIDTH, UI_HEIGHT


class NovaWindow(QMainWindow):
    sig_log        = pyqtSignal(str, str)
    sig_state      = pyqtSignal(str)
    sig_transcript = pyqtSignal(dict)
    sig_response   = pyqtSignal(dict)
    sig_nova_mode  = pyqtSignal(str)   # sleep/active mode transitions

    def __init__(self):
        super().__init__()
        self.setWindowTitle(UI_TITLE)
        self.resize(UI_WIDTH, UI_HEIGHT)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(MAIN_STYLESHEET)
        self._uploaded_file = None
        self._muted   = False
        self._tray    = None
        self._build_ui()
        self._start_clock()
        self._register_voice_callbacks()
        self.sig_log.connect(self._append_log)
        self.sig_state.connect(self._on_state)
        self.sig_transcript.connect(lambda d: self._append_log(d["who"], d["text"]))
        self.sig_response.connect(lambda d: self._append_log(d["who"], d["text"]))
        self.sig_nova_mode.connect(self._on_nova_mode_change)   # runs on Qt main thread ✓

    # ── Root layout ─────────────────────────────────────
    def _build_ui(self):
        central = QWidget(); central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        content = QWidget()
        content_lay = QHBoxLayout(content)
        content_lay.setContentsMargins(0, 0, 0, 0); content_lay.setSpacing(0)
        content_lay.addWidget(self._build_left())

        right_col = QWidget()
        right_col_lay = QVBoxLayout(right_col)
        right_col_lay.setContentsMargins(0, 0, 0, 0); right_col_lay.setSpacing(0)
        right_col_lay.addWidget(self._build_topbar())

        mid_row = QWidget()
        mid_lay = QHBoxLayout(mid_row)
        mid_lay.setContentsMargins(0, 0, 0, 0); mid_lay.setSpacing(0)
        mid_lay.addWidget(self._build_center(), 1)
        mid_lay.addWidget(self._build_right())
        right_col_lay.addWidget(mid_row, 1)

        content_lay.addWidget(right_col, 1)
        outer.addWidget(content, 1)
        outer.addWidget(self._build_bottombar())

    # ── LEFT PANEL ───────────────────────────────────────
    def _build_left(self):
        p = QWidget(); p.setObjectName("leftPanel"); p.setFixedWidth(280)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(18, 18, 18, 16); lay.setSpacing(14)

        header = QHBoxLayout(); header.setSpacing(10)
        icon_wrap = QFrame(); icon_wrap.setFixedSize(44, 44)
        icon_wrap.setStyleSheet("background:#00d4ff14; border:1px solid #00d4ff55; border-radius:10px;")
        icon_lay = QVBoxLayout(icon_wrap); icon_lay.setContentsMargins(0,0,0,0)
        icon_glyph = QLabel("◢◤")
        icon_glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_glyph.setStyleSheet("color:#00d4ff; font-size:14px; font-weight:bold;")
        icon_lay.addWidget(icon_glyph)
        header.addWidget(icon_wrap)

        title_col = QVBoxLayout(); title_col.setSpacing(0)
        t1 = QLabel("N.O.V.A"); t1.setObjectName("brandTitle")
        t2 = QLabel("NEURAL OPERATIVE\nVIRTUAL ASSISTANT"); t2.setObjectName("brandSubtitle")
        title_col.addWidget(t1); title_col.addWidget(t2)
        header.addLayout(title_col); header.addStretch()
        lay.addLayout(header)

        lay.addWidget(self._section_label("◈  SYSTEM STATUS"))
        self._sys_mon = SystemMonitor()
        lay.addWidget(self._sys_mon)
        lay.addWidget(self._divider())

        lay.addWidget(self._section_label("◈  CURRENT STATE"))
        state_row = QHBoxLayout(); state_row.setSpacing(10)
        self._state_icon = QLabel("∿")
        self._state_icon.setStyleSheet("color:#00d4ff; font-size:20px;")
        state_col = QVBoxLayout(); state_col.setSpacing(0)
        self._state_lbl = QLabel("LISTENING")
        self._state_lbl.setStyleSheet("color:#00d4ff; font-size:16px; font-weight:800; letter-spacing:1px;")
        self._state_sub = QLabel("NOVA-M ACTIVE")
        self._state_sub.setStyleSheet("color:#3c5a70; font-size:8px; letter-spacing:1px;")
        state_col.addWidget(self._state_lbl); state_col.addWidget(self._state_sub)
        state_row.addWidget(self._state_icon); state_row.addLayout(state_col); state_row.addStretch()
        lay.addLayout(state_row)

        lay.addWidget(self._section_label("AI ENGINE"))
        self._btn_gemini = self._eng_btn("GEMINI", Engine.GEMINI)
        self._btn_groq   = self._eng_btn("GROQ",   Engine.GROQ)
        self._btn_ollama = self._eng_btn("OLLAMA", Engine.OLLAMA)
        lay.addWidget(self._btn_gemini); lay.addWidget(self._btn_groq); lay.addWidget(self._btn_ollama)
        self._refresh_engine_btns()
        lay.addWidget(self._divider())

        self._nav_chat  = self._nav_item("💬  CHAT")
        self._nav_files = self._nav_item("📁  FILES")
        self._log_count = 0
        self._nav_log   = self._nav_item("☰  ACTIVITY LOG", badge="0")
        self._log_badge = self._nav_log._badge_lbl
        self._nav_settings = self._nav_item("⚙  SETTINGS")
        self._nav_chat.clicked.connect(lambda: self._cmd.setFocus())
        self._nav_files.clicked.connect(self._on_upload)
        self._nav_log.clicked.connect(self._open_history)
        self._nav_settings.clicked.connect(self._open_settings)
        for w in (self._nav_chat, self._nav_files, self._nav_log, self._nav_settings):
            lay.addWidget(w)

        lay.addStretch()
        self._sora_btn = QPushButton("⟳  SWITCH TO SORA")
        self._sora_btn.setObjectName("outlineBtn")
        self._sora_btn.setFixedHeight(34)
        self._sora_btn.clicked.connect(self._toggle_assistant)
        lay.addWidget(self._sora_btn)
        return p

    # ── TOP BAR ──────────────────────────────────────────
    def _build_topbar(self):
        bar = QWidget(); bar.setObjectName("topBar"); bar.setFixedHeight(64)
        lay = QHBoxLayout(bar); lay.setContentsMargins(24, 0, 20, 0); lay.setSpacing(14)

        status_dot = QLabel("●"); status_dot.setStyleSheet("color:#00d4ff; font-size:13px;")
        lay.addWidget(status_dot)

        greet_col = QVBoxLayout(); greet_col.setSpacing(2)
        self._greeting_lbl = QLabel("Good evening, Operator.")
        self._greeting_lbl.setObjectName("greetingLabel")
        status_row = QHBoxLayout(); status_row.setSpacing(6)
        self._status_text = QLabel("NOVA is listening and ready.")
        self._status_text.setObjectName("statusLabel")
        self._status_dot2 = QLabel("●")
        self._status_dot2.setStyleSheet("color:#22c55e; font-size:8px;")
        status_row.addWidget(self._status_text); status_row.addWidget(self._status_dot2); status_row.addStretch()
        greet_col.addWidget(self._greeting_lbl); greet_col.addLayout(status_row)
        lay.addLayout(greet_col); lay.addStretch()

        time_col = QVBoxLayout(); time_col.setSpacing(0)
        time_col.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._clock = QLabel("00:00:00"); self._clock.setObjectName("clockLabel")
        self._clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._date = QLabel("—"); self._date.setObjectName("dateLabel")
        self._date.setAlignment(Qt.AlignmentFlag.AlignRight)
        time_col.addWidget(self._clock); time_col.addWidget(self._date)
        lay.addLayout(time_col)

        bell_btn = self._icon_btn("🔔"); bell_btn.clicked.connect(self._open_history)
        settings_btn = self._icon_btn("⚙"); settings_btn.clicked.connect(self._open_settings)
        fs_btn = self._icon_btn("⛶"); fs_btn.clicked.connect(self._toggle_fs)
        for b in (bell_btn, settings_btn, fs_btn):
            lay.addWidget(b)
        return bar

    def _icon_btn(self, glyph: str) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setObjectName("iconButton")
        btn.setFixedSize(36, 36)
        return btn

    # ── CENTER PANEL ─────────────────────────────────────
    def _build_center(self):
        p = QWidget(); p.setObjectName("centerPanel")
        lay = QVBoxLayout(p)
        lay.setContentsMargins(30, 20, 30, 20); lay.setSpacing(14)

        self._vis = CircularVisualizer()
        lay.addWidget(self._vis, 1, Qt.AlignmentFlag.AlignCenter)

        input_row = QHBoxLayout(); input_row.setSpacing(10)
        self._cmd = QLineEdit()
        self._cmd.setObjectName("commandInput")
        self._cmd.setPlaceholderText("Type a command or question...")
        self._cmd.returnPressed.connect(self._on_send)
        input_row.addWidget(self._cmd, 1)
        send_btn = QPushButton("➤")
        send_btn.setObjectName("sendButton")
        send_btn.setFixedSize(46, 46)
        send_btn.clicked.connect(self._on_send)
        input_row.addWidget(send_btn)
        lay.addLayout(input_row)

        qa_row = QHBoxLayout(); qa_row.setSpacing(10)
        qa1 = QPushButton("📊  Summarize System")
        qa2 = QPushButton("📂  Open Recent Files")
        qa3 = QPushButton("🌐  Check Network")
        qa4 = QPushButton("🩺  Run Diagnostics")
        for b in (qa1, qa2, qa3, qa4):
            b.setObjectName("quickAction"); b.setFixedHeight(40)
            qa_row.addWidget(b)
        qa1.clicked.connect(self._quick_summarize_system)
        qa2.clicked.connect(self._on_upload)
        qa3.clicked.connect(self._quick_check_network)
        qa4.clicked.connect(self._quick_run_diagnostics)
        lay.addLayout(qa_row)

        self._wave = WaveformBar()
        lay.addWidget(self._wave)

        self._mic_btn = QPushButton("🎤  MICROPHONE ACTIVE")
        self._mic_btn.setObjectName("micPill")
        self._mic_btn.setFixedHeight(38)
        self._mic_btn.clicked.connect(self._on_mute)
        mic_row = QHBoxLayout()
        mic_row.addStretch(); mic_row.addWidget(self._mic_btn); mic_row.addStretch()
        lay.addLayout(mic_row)
        return p

    # ── RIGHT PANEL ──────────────────────────────────────
    def _build_right(self):
        p = QWidget(); p.setObjectName("rightPanel"); p.setFixedWidth(340)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(18, 18, 18, 18); lay.setSpacing(10)

        log_header = QHBoxLayout()
        log_title = QLabel("▲  ACTIVITY LOG")
        log_title.setStyleSheet("color:#c5dce8; font-size:11px; font-weight:700; letter-spacing:1px;")
        clear_btn = QPushButton("CLEAR")
        clear_btn.setObjectName("clearBtn")
        clear_btn.setFixedSize(54, 22)
        clear_btn.clicked.connect(self._clear_log)
        log_header.addWidget(log_title); log_header.addStretch(); log_header.addWidget(clear_btn)
        lay.addLayout(log_header)

        self._log_scroll = QScrollArea()
        self._log_scroll.setWidgetResizable(True)
        self._log_container = QWidget()
        self._log_lay = QVBoxLayout(self._log_container)
        self._log_lay.setSpacing(2)
        self._log_lay.addStretch()
        self._log_scroll.setWidget(self._log_container)
        lay.addWidget(self._log_scroll, 1)

        view_full = QPushButton("VIEW FULL LOG  ⤴")
        view_full.setObjectName("outlineBtn")
        view_full.setFixedHeight(28)
        view_full.clicked.connect(self._open_history)
        lay.addWidget(view_full)
        lay.addWidget(self._divider())

        lay.addWidget(self._section_label("FILE UPLOAD"))
        self._upload_btn = QPushButton(
            "⬆\n\nDrop files here or click to browse\nImages · Video · Audio · PDF · Docs · Code"
        )
        self._upload_btn.setObjectName("uploadZone")
        self._upload_btn.setFixedHeight(110)
        self._upload_btn.clicked.connect(self._on_upload)
        lay.addWidget(self._upload_btn)

        self._upload_lbl = QLabel("No file loaded")
        self._upload_lbl.setStyleSheet("color:#3c5a70; font-size:9px;")
        self._upload_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._upload_lbl)
        return p

    # ── BOTTOM BAR ───────────────────────────────────────
    def _build_bottombar(self):
        bar = QWidget(); bar.setObjectName("bottomBar"); bar.setFixedHeight(34)
        lay = QHBoxLayout(bar); lay.setContentsMargins(20, 0, 20, 0)

        left = QHBoxLayout(); left.setSpacing(10)
        v_lbl = QLabel("NOVA Core v5.3"); v_lbl.setStyleSheet("color:#3c5a70; font-size:9px;")
        sec_lbl = QLabel("✓ Sec Cleared"); sec_lbl.setStyleSheet("color:#22c55e; font-size:9px; font-weight:700;")
        left.addWidget(v_lbl); left.addWidget(sec_lbl)
        lay.addLayout(left); lay.addStretch()

        brand = QLabel("▲  AADARSH LABS")
        brand.setStyleSheet("color:#3c5a70; font-size:9px; font-weight:700; letter-spacing:2px;")
        lay.addWidget(brand); lay.addStretch()

        secure_lbl = QLabel("●  SECURE  🔒")
        secure_lbl.setStyleSheet("color:#22c55e; font-size:9px; font-weight:700;")
        lay.addWidget(secure_lbl)
        return bar

    # ── Helpers ──────────────────────────────────────────
    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text); lbl.setObjectName("sectionHeader")
        return lbl

    def _divider(self) -> QFrame:
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background:#122638; max-height:1px; border:none;")
        return f

    def _nav_item(self, text: str, badge: str = None) -> QPushButton:
        btn = QPushButton()
        btn.setObjectName("navItem")
        btn.setFixedHeight(34)
        row = QHBoxLayout(btn)
        row.setContentsMargins(10, 0, 10, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size:11px; font-weight:600; background:transparent; color:#5a7a90;")
        row.addWidget(lbl); row.addStretch()
        btn._badge_lbl = None
        if badge is not None:
            badge_lbl = QLabel(badge)
            badge_lbl.setFixedSize(22, 16)
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_lbl.setStyleSheet(
                "background:#00d4ff22; border:1px solid #00d4ff55; border-radius:8px;"
                "color:#00d4ff; font-size:8px; font-weight:700;"
            )
            row.addWidget(badge_lbl)
            btn._badge_lbl = badge_lbl
        return btn

    def _eng_btn(self, label: str, engine_val: str) -> QPushButton:
        btn = QPushButton(f"○  {label}")
        btn.setFixedHeight(32)
        btn.clicked.connect(lambda _, e=engine_val: self._on_engine(e))
        return btn

    def _refresh_engine_btns(self):
        eng = get_engine()
        mapping = {Engine.GEMINI: self._btn_gemini, Engine.GROQ: self._btn_groq, Engine.OLLAMA: self._btn_ollama}
        for e, btn in mapping.items():
            label = btn.text().split("  ", 1)[-1]
            if e == eng:
                btn.setObjectName("engineRowActive"); btn.setText(f"●  {label}")
            else:
                btn.setObjectName("engineRow"); btn.setText(f"○  {label}")
            btn.style().unpolish(btn); btn.style().polish(btn)

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
        self._date.setText(n.strftime("%a, %d %b %Y"))
        self._update_greeting()

    def _update_greeting(self):
        hour = datetime.datetime.now().hour
        if hour < 12:   greet = "Good morning, Boss!"
        elif hour < 17: greet = "Good afternoon, Boss!"
        else:           greet = "Good evening, Boss!"
        self._greeting_lbl.setText(greet)

    # ── Activity log ──────────────────────────────────────
    def _append_log(self, who, text):
        entry = LogEntry(who, text)
        self._log_lay.insertWidget(self._log_lay.count() - 1, entry)
        self._log_count += 1
        if self._log_badge:
            self._log_badge.setText(str(self._log_count))
        QTimer.singleShot(10, lambda: self._log_scroll.verticalScrollBar().setValue(
            self._log_scroll.verticalScrollBar().maximum()
        ))
        while self._log_lay.count() > 101:
            item = self._log_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_log(self):
        while self._log_lay.count() > 1:
            item = self._log_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._log_count = 0
        if self._log_badge:
            self._log_badge.setText("0")

    # ── State ─────────────────────────────────────────────
    def _on_state(self, state):
        status_map = {
            VoiceState.LISTENING: ("LISTENING", "NOVA is listening and ready.", "#00d4ff"),
            VoiceState.SPEAKING:  ("SPEAKING",  "NOVA is responding.",          "#22c55e"),
            VoiceState.THINKING:  ("THINKING",  "NOVA is processing...",        "#fbbf24"),
            VoiceState.IDLE:      ("STANDBY",   "NOVA is on standby.",          "#3c5a70"),
            VoiceState.SLEEPING:  ("SLEEPING",  "Say 'Nova' to wake up.",       "#fbbf24"),
        }
        label, status_text, color = status_map.get(state, ("STANDBY", "NOVA is on standby.", "#3c5a70"))
        self._state_lbl.setText(label)
        self._state_lbl.setStyleSheet(f"color:{color}; font-size:16px; font-weight:800; letter-spacing:1px;")
        self._status_text.setText(status_text)
        self._status_dot2.setStyleSheet(f"color:{color}; font-size:8px;")

        asst = get_assistant()
        self._vis.set_state(state);  self._vis.set_assistant(asst)
        self._wave.set_state(state); self._wave.set_assistant(asst)
        self._state_sub.setText("NOVA-M ACTIVE" if asst == "nova" else "SORA-F ACTIVE")
        self._sora_btn.setText("⟳  SWITCH TO NOVA" if asst == "sora" else "⟳  SWITCH TO SORA")

    # ── Engine ────────────────────────────────────────────
    def _on_engine(self, engine):
        set_engine(engine)
        self._refresh_engine_btns()
        names = {Engine.GEMINI:"GEMINI", Engine.GROQ:"GROQ", Engine.OLLAMA:"OLLAMA"}
        self._append_log("sys", f"Engine switched to {names.get(engine, engine)}.")

    # ── Toggle assistant ──────────────────────────────────
    def _toggle_assistant(self):
        if get_assistant() == "nova":
            set_assistant("sora")
            self._append_log("sys", "Switched to SORA.")
            speak_sora("SORA online.")
        else:
            set_assistant("nova")
            self._append_log("sys", "Switched to NOVA.")
            speak_nova("NOVA online.")
        self._on_state(VoiceState.IDLE)

    # ── Send text ─────────────────────────────────────────
    def _on_send(self):
        text = self._cmd.text().strip()
        if not text:
            return
        self._cmd.clear()
        self._append_log("user", text)

        if self._uploaded_file:
            text = f"[File: {Path(self._uploaded_file).name}] {text}"

        asst = get_assistant()

        def _run():
            from core.command_router import route
            from core.logger import log
            try:
                route(asst, text)
            except SystemExit:
                pass
            except Exception as e:
                log.error(f"[TextCommand] Route failed for '{text[:40]}': {e}", exc_info=True)
                from core.voice import speak
                speak("Something went wrong. Please try again.")

        threading.Thread(target=_run, daemon=True, name="TextCmd").start()

    # ── Upload ────────────────────────────────────────────
    def _on_upload(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Upload File", str(Path.home()),
            "All Files (*.*);;Images (*.jpg *.jpeg *.png *.gif *.bmp *.webp);;"
            "PDFs (*.pdf);;Code (*.py *.js *.html *.css *.java *.cpp *.ts *.sql);;"
            "Text (*.txt *.md *.csv *.json)"
        )
        if path:
            self._set_uploaded(path)

    def _set_uploaded(self, path: str) -> None:
        self._uploaded_file = path
        fname = Path(path).name
        self._upload_lbl.setText(f"✓ {fname}")
        self._upload_lbl.setStyleSheet("color:#00d4ff; font-size:9px;")
        self._append_log("sys", f"File loaded: {fname}")
        self._trigger_file_analysis(path)

    def _trigger_file_analysis(self, filepath: str) -> None:
        from actions.file_analyzer import load_and_announce
        threading.Thread(target=load_and_announce, args=(filepath,), daemon=True, name="FileAnalyzer").start()

    # ── Quick actions (run off-thread to avoid blocking the UI) ──
    def _quick_summarize_system(self):
        threading.Thread(target=self._do_summarize_system, daemon=True).start()

    def _do_summarize_system(self):
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory().percent
        speak(f"System summary: CPU at {int(cpu)} percent, memory at {int(mem)} percent. All systems nominal.")

    def _quick_check_network(self):
        threading.Thread(target=self._do_check_network, daemon=True).start()

    def _do_check_network(self):
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            speak("Network connection is stable and active.")
        except OSError:
            speak("I couldn't reach the internet. Please check your network connection.")

    def _quick_run_diagnostics(self):
        threading.Thread(target=self._do_run_diagnostics, daemon=True).start()

    def _do_run_diagnostics(self):
        import psutil
        cpu  = psutil.cpu_percent(interval=0.3)
        mem  = psutil.virtual_memory().percent
        disk = psutil.disk_usage("C:\\").percent
        bat  = psutil.sensors_battery()
        bat_txt = f", battery at {int(bat.percent)} percent" if bat else ""
        speak(
            f"Diagnostics complete. CPU {int(cpu)} percent, memory {int(mem)} percent, "
            f"disk {int(disk)} percent used{bat_txt}. No issues detected."
        )

    # ── Mute ──────────────────────────────────────────────
    def _on_mute(self):
        from core.voice import stop_audio_loop, audio_loop
        self._muted = not self._muted
        if self._muted:
            stop_audio_loop()
            self._mic_btn.setText("🔇  MICROPHONE MUTED")
            self._mic_btn.setObjectName("micPillMuted")
            self._append_log("sys", "Microphone muted.")
        else:
            threading.Thread(target=audio_loop, daemon=True).start()
            self._mic_btn.setText("🎤  MICROPHONE ACTIVE")
            self._mic_btn.setObjectName("micPill")
            self._append_log("sys", "Microphone active.")
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)

    # ── Fullscreen ────────────────────────────────────────
    def _toggle_fs(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # ── Panels ────────────────────────────────────────────
    def _open_settings(self) -> None:
        from ui.settings_panel import SettingsPanel
        SettingsPanel(self).exec()

    def _open_history(self) -> None:
        from ui.history_search import HistorySearchPanel
        HistorySearchPanel(self).exec()

    # ── Keys ──────────────────────────────────────────────
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F11: self._toggle_fs()
        elif event.key() == Qt.Key.Key_F4: self._on_mute()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen(): self.showNormal()
        else: super().keyPressEvent(event)

    # ── Close → minimise to tray ──────────────────────────
    def closeEvent(self, event) -> None:
        if self._tray:
            event.ignore()
            self.hide()
            self._tray.notify("N.O.V.A", "Running in the background.\nDouble-click the tray icon to restore.")
        else:
            event.accept()

    # ── Drag & Drop ───────────────────────────────────────
    def showEvent(self, e):
        super().showEvent(e); self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self._set_uploaded(urls[0].toLocalFile())

    def _register_voice_callbacks(self):
        voice_on("state_change", lambda s: self.sig_state.emit(s))
        voice_on("transcript",   lambda d: self.sig_transcript.emit(d))
        voice_on("response",     lambda d: self.sig_response.emit(d))
        voice_on("nova_state",   lambda s: self._on_nova_mode_change(s))
    
    # REPLACE WITH:
    def _on_nova_mode_change(self, mode: str) -> None:
        """
        Called when NOVA transitions between sleep and active modes.
        Runs on Qt main thread via sig_nova_mode signal — no QObject crash.
        """
        from core.voice import NovaState, VoiceState
        if mode == NovaState.SLEEP:
            self.sig_state.emit(VoiceState.SLEEPING)
            self._state_sub.setText("NOVA-M ACTIVE")
            self._append_log("sys", "NOVA entering sleep mode.")
        else:
            self.sig_state.emit(VoiceState.LISTENING)
            self._state_sub.setText("NOVA-M ACTIVE")
            self._append_log("sys", "NOVA activated.")

    def _update_countdown(self) -> None:
        """Update the sub-label with remaining active time."""
        from core.voice import _active_until, NovaState, _nova_state
        if _nova_state != NovaState.ACTIVE:
            if hasattr(self, "_countdown_timer"):
                self._countdown_timer.stop()
            return
        remaining = max(0, int(_active_until - __import__("time").time()))
        mins      = remaining // 60
        secs      = remaining % 60
        self._state_sub.setText(f"ACTIVE — {mins}:{secs:02d} remaining")

    def _register_voice_callbacks(self):
        voice_on("state_change", lambda s: self.sig_state.emit(s))
        voice_on("transcript",   lambda d: self.sig_transcript.emit(d))
        voice_on("response",     lambda d: self.sig_response.emit(d))
        # Route through pyqtSignal — ensures _on_nova_mode_change runs on
        # the Qt main thread, not the audio_loop thread (fixes QObject crash)
        voice_on("nova_state",   lambda s: self.sig_nova_mode.emit(s))