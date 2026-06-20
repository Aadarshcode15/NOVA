# ui/history_search.py
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QScrollArea, QWidget, QFrame
)
from PyQt6.QtCore import Qt

_STYLE = """
QDialog {
    background-color: #08111c;
    color: #a0cfe0;
    font-family: 'Courier New', monospace;
}
QLineEdit {
    background: #040810;
    border: 1px solid #1a3a50;
    color: #a0cfe0;
    padding: 8px 12px;
    font-family: 'Courier New', monospace;
    font-size: 12px;
}
QLineEdit:focus { border: 1px solid #00c8ff77; }
QPushButton#search {
    background: #00c8ff22;
    border: 1px solid #00c8ff66;
    color: #00c8ff;
    padding: 8px 18px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
    font-weight: bold;
}
QPushButton#search:hover { background: #00c8ff44; }
QScrollArea { border: none; background: transparent; }
QLabel#empty {
    color: #2a4a5e;
    font-size: 11px;
}
"""


def _format_time(ts_str: str) -> str:
    try:
        dt  = datetime.fromisoformat(ts_str)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("Today, %I:%M %p").replace(" 0", " ")
        if (now.date() - dt.date()).days == 1:
            return dt.strftime("Yesterday, %I:%M %p").replace(" 0", " ")
        return dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")
    except Exception:
        return ts_str


class _ResultCard(QFrame):
    def __init__(self, timestamp: str, assistant: str, role: str, content: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame{background:#0a1220;border:1px solid #1a3a50;border-radius:2px;}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)

        header    = QHBoxLayout()
        who_color = "#f0a500" if role == "user" else (
            "#00c8ff" if assistant == "nova" else "#c084fc"
        )
        who_text  = "You" if role == "user" else assistant.upper()
        who_lbl   = QLabel(who_text)
        who_lbl.setStyleSheet(f"color:{who_color};font-size:10px;font-weight:bold;letter-spacing:1px;")
        time_lbl  = QLabel(_format_time(timestamp))
        time_lbl.setStyleSheet("color:#2a4a5e;font-size:9px;")
        header.addWidget(who_lbl)
        header.addStretch()
        header.addWidget(time_lbl)
        lay.addLayout(header)

        content_lbl = QLabel(content[:300] + ("..." if len(content) > 300 else ""))
        content_lbl.setWordWrap(True)
        content_lbl.setStyleSheet("color:#a0cfe0;font-size:11px;")
        lay.addWidget(content_lbl)


class HistorySearchPanel(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("N.O.V.A — Conversation History")
        self.setFixedSize(560, 600)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._show_recent()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("🔍  SEARCH CONVERSATION HISTORY")
        title.setStyleSheet("color:#00c8ff;font-size:12px;font-weight:bold;letter-spacing:3px;")
        root.addWidget(title)

        row = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search what you've said to NOVA...")
        self._search_box.returnPressed.connect(self._do_search)
        search_btn = QPushButton("SEARCH")
        search_btn.setObjectName("search")
        search_btn.clicked.connect(self._do_search)
        row.addWidget(self._search_box, 1)
        row.addWidget(search_btn)
        root.addLayout(row)

        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet("color:#2a4a5e;font-size:9px;letter-spacing:1px;")
        root.addWidget(self._stats_lbl)

        self._scroll          = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._results_widget  = QWidget()
        self._results_layout  = QVBoxLayout(self._results_widget)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch()
        self._scroll.setWidget(self._results_widget)
        root.addWidget(self._scroll, 1)

    def _clear_results(self) -> None:
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_recent(self) -> None:
        from core.conversation_log import get_recent, get_stats
        rows  = get_recent(limit=20)
        stats = get_stats()
        since = f" since {stats['since'][:10]}" if stats["since"] else ""
        self._stats_lbl.setText(f"{stats['total']} messages logged{since}")
        self._populate(rows, "No conversation history yet.")

    def _do_search(self) -> None:
        from core.conversation_log import search
        text = self._search_box.text().strip()
        if not text:
            self._show_recent()
            return
        rows = search(text, limit=20)
        self._stats_lbl.setText(f'{len(rows)} result{"s" if len(rows) != 1 else ""} for "{text}"')
        self._populate(rows, f'No results found for "{text}".')

    def _populate(self, rows: list, empty_msg: str) -> None:
        self._clear_results()
        if not rows:
            empty = QLabel(empty_msg)
            empty.setObjectName("empty")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._results_layout.insertWidget(0, empty)
            return
        for ts, assistant, role, content in rows:
            card = _ResultCard(ts, assistant, role, content)
            self._results_layout.insertWidget(self._results_layout.count() - 1, card)