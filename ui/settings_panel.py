# ui/settings_panel.py
import os
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QWidget, QLabel, QComboBox, QLineEdit, QCheckBox,
    QPushButton, QSlider, QFrame, QSizePolicy, QTimeEdit,
    QScrollArea, QGridLayout
)
from PyQt6.QtCore  import Qt, QTime
from PyQt6.QtGui   import QFont, QColor
from config.settings import BASE_DIR


# ── Stylesheet matching NOVA dark theme ───────────────────
_STYLE = """
QDialog {
    background-color: #08111c;
    color: #a0cfe0;
    font-family: 'Courier New', monospace;
}
QTabWidget::pane {
    border: 1px solid #1a3a50;
    background: #08111c;
}
QTabBar::tab {
    background: #050a10;
    color: #2a4a5e;
    border: 1px solid #1a3a50;
    padding: 8px 18px;
    font-family: 'Courier New', monospace;
    font-size: 10px;
    letter-spacing: 2px;
}
QTabBar::tab:selected {
    background: #0a1a2e;
    color: #00c8ff;
    border-bottom: 2px solid #00c8ff;
}
QTabBar::tab:hover { color: #00c8ff88; }
QLabel {
    color: #a0cfe0;
    font-size: 11px;
    font-family: 'Courier New', monospace;
}
QLabel#section {
    color: #2a4a5e;
    font-size: 9px;
    letter-spacing: 3px;
}
QComboBox {
    background: #040810;
    border: 1px solid #1a3a50;
    color: #a0cfe0;
    padding: 5px 10px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
}
QComboBox:hover { border: 1px solid #00c8ff55; }
QComboBox QAbstractItemView {
    background: #08111c;
    color: #a0cfe0;
    selection-background-color: #00c8ff22;
}
QLineEdit {
    background: #040810;
    border: 1px solid #1a3a50;
    color: #a0cfe0;
    padding: 5px 10px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
}
QLineEdit:focus { border: 1px solid #00c8ff77; }
QCheckBox {
    color: #a0cfe0;
    font-size: 11px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #1a3a50;
    background: #040810;
}
QCheckBox::indicator:checked {
    background: #00c8ff;
    border: 1px solid #00c8ff;
}
QSlider::groove:horizontal {
    background: #1a3a50;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00c8ff;
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #00c8ff; border-radius: 2px; }
QPushButton#save {
    background: #00c8ff22;
    border: 1px solid #00c8ff66;
    color: #00c8ff;
    padding: 8px 24px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    letter-spacing: 2px;
    font-weight: bold;
}
QPushButton#save:hover { background: #00c8ff44; border: 1px solid #00c8ff; }
QPushButton#cancel {
    background: transparent;
    border: 1px solid #1a3a50;
    color: #2a4a5e;
    padding: 8px 24px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    letter-spacing: 2px;
}
QPushButton#cancel:hover { border: 1px solid #00c8ff55; color: #00c8ff; }
QPushButton#action {
    background: transparent;
    border: 1px solid #1a3a50;
    color: #a0cfe0;
    padding: 5px 14px;
    font-family: 'Courier New', monospace;
    font-size: 10px;
}
QPushButton#action:hover { border: 1px solid #00c8ff55; color: #00c8ff; }
QTimeEdit {
    background: #040810;
    border: 1px solid #1a3a50;
    color: #a0cfe0;
    padding: 4px 8px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
}
"""


class SettingsPanel(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("N.O.V.A — Settings")
        self.setFixedSize(560, 520)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        from config.user_config import load
        self._cfg = load()

        self._build_ui()

    # ── Build UI ───────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet("background:#050a10; border-bottom:1px solid #1a3a50;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title = QLabel("⚙  SETTINGS")
        title.setStyleSheet("color:#00c8ff;font-size:12px;font-weight:bold;letter-spacing:4px;")
        hl.addWidget(title)
        hl.addStretch()
        root.addWidget(header)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._tab_ai(),       "AI")
        self._tabs.addTab(self._tab_voice(),     "VOICE")
        self._tabs.addTab(self._tab_briefing(),  "BRIEFING")
        self._tabs.addTab(self._tab_apikeys(),   "API KEYS")
        self._tabs.addTab(self._tab_general(),   "GENERAL")
        root.addWidget(self._tabs, 1)

        # Footer buttons
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background:#050a10;border-top:1px solid #1a3a50;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 0, 16, 0)
        fl.addStretch()
        cancel_btn = QPushButton("CANCEL"); cancel_btn.setObjectName("cancel")
        save_btn   = QPushButton("SAVE & APPLY"); save_btn.setObjectName("save")
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self._save_and_apply)
        fl.addWidget(cancel_btn)
        fl.addSpacing(8)
        fl.addWidget(save_btn)
        root.addWidget(footer)

    # ── Tab: AI ────────────────────────────────────────────

    def _tab_ai(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(16)

        lay.addWidget(self._section("DEFAULT ENGINE"))
        self._engine_combo = QComboBox()
        self._engine_combo.addItems(["groq", "gemini", "ollama"])
        self._engine_combo.setCurrentText(self._cfg["ai"].get("default_engine", "groq"))
        lay.addWidget(self._row("Active engine", self._engine_combo))

        lay.addWidget(self._divider())
        lay.addWidget(self._section("OLLAMA LOCAL MODEL"))
        self._ollama_model = QLineEdit(self._cfg["ai"].get("ollama_model", "gemma3:4b"))
        self._ollama_model.setPlaceholderText("e.g. gemma3:4b or llama3.2:3b")
        lay.addWidget(self._row("Model name", self._ollama_model))

        note = QLabel("Changes apply immediately. Ollama model requires restart.")
        note.setStyleSheet("color:#2a4a5e; font-size:9px; letter-spacing:1px;")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch()
        return w

    # ── Tab: Voice ─────────────────────────────────────────

    def _tab_voice(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(16)

        lay.addWidget(self._section("LANGUAGE"))
        self._lang_combo = QComboBox()
        self._lang_combo.addItems(["en — English", "hi — Hindi", "mr — Marathi"])
        lang_map = {"en": 0, "hi": 1, "mr": 2}
        self._lang_combo.setCurrentIndex(lang_map.get(self._cfg["voice"].get("language","en"), 0))
        lay.addWidget(self._row("Response language", self._lang_combo))

        lay.addWidget(self._divider())
        lay.addWidget(self._section("WHISPER STT MODEL"))
        self._whisper_combo = QComboBox()
        self._whisper_combo.addItems(["tiny.en", "base.en", "small.en", "medium.en"])
        self._whisper_combo.setCurrentText(self._cfg["voice"].get("whisper_model", "small.en"))
        lay.addWidget(self._row("Model size", self._whisper_combo))

        lay.addWidget(self._divider())
        lay.addWidget(self._section("MICROPHONE SENSITIVITY"))
        slider_row = QHBoxLayout()
        self._threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self._threshold_slider.setRange(200, 2000)
        threshold = self._cfg["voice"].get("energy_threshold", 600)
        self._threshold_slider.setValue(threshold)
        self._threshold_label = QLabel(str(threshold))
        self._threshold_label.setFixedWidth(45)
        self._threshold_label.setStyleSheet("color:#00c8ff;")
        self._threshold_slider.valueChanged.connect(
            lambda v: self._threshold_label.setText(str(v))
        )
        slider_row.addWidget(self._threshold_slider)
        slider_row.addWidget(self._threshold_label)
        lay.addLayout(slider_row)
        note = QLabel("Lower = more sensitive. Higher = ignores background noise. Default: 600")
        note.setStyleSheet("color:#2a4a5e; font-size:9px;")
        lay.addWidget(note)

        note2 = QLabel("Whisper model change requires restart.")
        note2.setStyleSheet("color:#2a4a5e; font-size:9px;")
        lay.addWidget(note2)
        lay.addStretch()
        return w

    # ── Tab: Briefing ──────────────────────────────────────

    def _tab_briefing(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(16)

        lay.addWidget(self._section("DAILY BRIEFING TIME"))
        b = self._cfg.get("briefing", {})
        t_str = b.get("time", "08:00")
        h, m  = map(int, t_str.split(":"))
        self._briefing_time = QTimeEdit()
        self._briefing_time.setTime(QTime(h, m))
        self._briefing_time.setDisplayFormat("HH:mm")
        self._briefing_time.setFixedWidth(80)
        lay.addWidget(self._row("Trigger time (24h)", self._briefing_time))

        lay.addWidget(self._divider())
        lay.addWidget(self._section("BRIEFING SECTIONS"))

        self._brief_weather  = QCheckBox("Weather forecast")
        self._brief_calendar = QCheckBox("Calendar events")
        self._brief_todo     = QCheckBox("To-do list")
        self._brief_news     = QCheckBox("Top news headlines")

        self._brief_weather.setChecked(b.get("weather",  True))
        self._brief_calendar.setChecked(b.get("calendar", True))
        self._brief_todo.setChecked(b.get("todo",     True))
        self._brief_news.setChecked(b.get("news",     False))

        for cb in [self._brief_weather, self._brief_calendar,
                   self._brief_todo, self._brief_news]:
            lay.addWidget(cb)

        note = QLabel('Trigger anytime: say "Nova, morning briefing"')
        note.setStyleSheet("color:#2a4a5e; font-size:9px; letter-spacing:1px;")
        lay.addWidget(note)
        lay.addStretch()
        return w

    # ── Tab: API Keys ──────────────────────────────────────

    def _tab_apikeys(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(12)

        from config.settings import (
            GEMINI_API_KEY, GROQ_API_KEY, WEATHER_API_KEY,
            NEWS_API_KEY, SPOTIFY_CLIENT_ID
        )

        keys = [
            ("Gemini API",       GEMINI_API_KEY,     "aistudio.google.com/app/apikey"),
            ("Groq API",         GROQ_API_KEY,        "console.groq.com"),
            ("OpenWeatherMap",   WEATHER_API_KEY,     "openweathermap.org/api"),
            ("GNews",            NEWS_API_KEY,         "gnews.io"),
            ("Spotify Client",   SPOTIFY_CLIENT_ID,   "developer.spotify.com/dashboard"),
        ]

        lay.addWidget(self._section("KEY STATUS"))

        for name, value, url in keys:
            row = QHBoxLayout()
            status = "●" if value else "○"
            color  = "#00ff88" if value else "#ff3355"
            dot = QLabel(status)
            dot.setFixedWidth(18)
            dot.setStyleSheet(f"color:{color}; font-size:14px;")
            lbl = QLabel(name)
            lbl.setFixedWidth(160)
            masked = ("*" * 8 + value[-4:]) if len(value) > 4 else ("Not set" if not value else value)
            val = QLabel(masked)
            val.setStyleSheet("color:#2a4a5e; font-size:10px;")
            row.addWidget(dot)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            lay.addLayout(row)

        lay.addWidget(self._divider())

        env_btn = QPushButton("📄  Open .env in Editor")
        env_btn.setObjectName("action")
        env_btn.clicked.connect(self._open_env)
        lay.addWidget(env_btn)

        note = QLabel("API key changes take effect after restarting NOVA.")
        note.setStyleSheet("color:#2a4a5e; font-size:9px;")
        lay.addWidget(note)
        lay.addStretch()
        return w

    # ── Tab: General ───────────────────────────────────────

    def _tab_general(self) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(20, 20, 20, 20); lay.setSpacing(16)

        lay.addWidget(self._section("WINDOW BEHAVIOUR"))
        self._minimize_tray = QCheckBox("Minimise to tray when window is closed")
        self._minimize_tray.setChecked(
            self._cfg.get("general", {}).get("minimize_to_tray", True)
        )
        lay.addWidget(self._minimize_tray)

        lay.addWidget(self._divider())
        lay.addWidget(self._section("NOVA VERSION"))
        version_info = [
            ("Version",  "v2.5 — Sprint 4"),
            ("Python",   f"{__import__('sys').version.split()[0]}"),
            ("Platform", "Windows"),
            ("Log dir",  str(BASE_DIR / "logs")),
        ]
        for label, value in version_info:
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(100)
            lbl.setStyleSheet("color:#2a4a5e; font-size:10px;")
            val = QLabel(value)
            val.setStyleSheet("color:#a0cfe0; font-size:10px;")
            row.addWidget(lbl); row.addWidget(val, 1)
            lay.addLayout(row)

        lay.addWidget(self._divider())
        open_log_btn = QPushButton("📋  Open Latest Log File")
        open_log_btn.setObjectName("action")
        open_log_btn.clicked.connect(self._open_latest_log)
        lay.addWidget(open_log_btn)

        lay.addWidget(self._divider())
        lay.addWidget(self._section("CONVERSATION HISTORY"))
        from core.conversation_log import get_stats
        stats = get_stats()
        history_stats = QLabel(f"{stats['total']} messages stored")
        history_stats.setStyleSheet("color:#2a4a5e; font-size:10px;")
        lay.addWidget(history_stats)

        clear_history_btn = QPushButton("🗑  Clear All Conversation History")
        clear_history_btn.setObjectName("action")
        clear_history_btn.clicked.connect(self._clear_history)
        lay.addWidget(clear_history_btn)

        lay.addStretch()
        return w

    def _clear_history(self) -> None:
        from core.conversation_log import clear_all
        count = clear_all()
        from core.voice import speak
        speak(f"Cleared {count} stored messages.")
        self.accept()
    
        

    # ── Save & Apply ───────────────────────────────────────

    def _save_and_apply(self) -> None:
        from config import user_config as uc

        # ── Read values from UI ──
        lang_text = self._lang_combo.currentText().split(" — ")[0]
        t         = self._briefing_time.time()
        time_str  = f"{t.hour():02d}:{t.minute():02d}"

        new_cfg = {
            "ai": {
                "default_engine": self._engine_combo.currentText(),
                "ollama_model":   self._ollama_model.text().strip(),
            },
            "voice": {
                "language":         lang_text,
                "whisper_model":    self._whisper_combo.currentText(),
                "energy_threshold": self._threshold_slider.value(),
            },
            "briefing": {
                "time":     time_str,
                "weather":  self._brief_weather.isChecked(),
                "calendar": self._brief_calendar.isChecked(),
                "todo":     self._brief_todo.isChecked(),
                "news":     self._brief_news.isChecked(),
            },
            "general": {
                "minimize_to_tray": self._minimize_tray.isChecked(),
            },
        }

        uc.save(new_cfg)

        # ── Apply immediately (no restart needed) ──
        uc.apply_engine(new_cfg["ai"]["default_engine"])
        uc.apply_language(new_cfg["voice"]["language"])
        uc.apply_energy_threshold(new_cfg["voice"]["energy_threshold"])
        uc.apply_briefing_time(time_str)
        uc.apply_briefing_sections({
            "weather":  new_cfg["briefing"]["weather"],
            "calendar": new_cfg["briefing"]["calendar"],
            "todo":     new_cfg["briefing"]["todo"],
            "news":     new_cfg["briefing"]["news"],
        })

        from core.voice import speak
        speak("Settings saved.")
        self.accept()

    # ── Helper widgets ─────────────────────────────────────

    def _section(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("section")
        return lbl

    def _divider(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("background:#1a3a50; max-height:1px; border:none;")
        return f

    def _row(self, label: str, widget) -> QWidget:
        w = QWidget(); lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label); lbl.setFixedWidth(200)
        lay.addWidget(lbl); lay.addWidget(widget, 1)
        return w

    # ── Actions ────────────────────────────────────────────

    def _open_env(self) -> None:
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            env_path.write_text("# NOVA environment variables\n")
        os.startfile(str(env_path))

    def _open_latest_log(self) -> None:
        log_dir = BASE_DIR / "logs"
        logs    = sorted(log_dir.glob("session_*.log"))
        if logs:
            os.startfile(str(logs[-1]))