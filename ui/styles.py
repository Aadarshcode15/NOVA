# ui/styles.py
MAIN_STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Arial', sans-serif;
    color: #c5dce8;
    selection-background-color: #00d4ff33;
}
QMainWindow, QWidget#centralWidget {
    background-color: #04070d;
}
QWidget { background-color: transparent; }

/* ── Panels ── */
QWidget#leftPanel {
    background-color: #070c16;
    border-right: 1px solid #0f2536;
}
QWidget#rightPanel {
    background-color: #070c16;
    border-left: 1px solid #0f2536;
}
QWidget#centerPanel { background-color: #04070d; }

QWidget#topBar {
    background-color: #060a13;
    border-bottom: 1px solid #0f2536;
}
QWidget#bottomBar {
    background-color: #050910;
    border-top: 1px solid #0f2536;
}

/* ── Labels ── */
QLabel#brandTitle {
    color: #00d4ff;
    font-size: 19px;
    font-weight: 800;
    letter-spacing: 3px;
}
QLabel#brandSubtitle {
    color: #3c5a70;
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 2px;
}
QLabel#greetingLabel {
    color: #00d4ff;
    font-size: 14px;
    font-weight: 700;
}
QLabel#statusLabel {
    color: #5a7a90;
    font-size: 10px;
}
QLabel#clockLabel {
    color: #e0f4ff;
    font-size: 19px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#dateLabel {
    color: #3c5a70;
    font-size: 9px;
}
QLabel#sectionHeader {
    color: #4a6478;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
}

/* ── Scroll areas ── */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 6px; border: none;
}
QScrollBar::handle:vertical {
    background: #16334a; border-radius: 3px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #00d4ff66; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

/* ── Input ── */
QLineEdit#commandInput {
    background-color: #0a121f;
    border: 1px solid #16334a;
    border-radius: 10px;
    color: #e0f4ff;
    font-size: 12px;
    padding: 12px 16px;
}
QLineEdit#commandInput:focus { border: 1px solid #00d4ff88; }
QLineEdit#commandInput::placeholder { color: #3c5a70; }

/* ── Buttons ── */
QPushButton#sendButton {
    background-color: #00d4ff22;
    border: 1px solid #00d4ff66;
    border-radius: 10px;
    color: #00d4ff;
    font-size: 14px;
    font-weight: bold;
}
QPushButton#sendButton:hover { background-color: #00d4ff44; }

QPushButton#iconButton {
    background-color: #0a121f;
    border: 1px solid #16334a;
    border-radius: 9px;
    color: #5a7a90;
    font-size: 13px;
}
QPushButton#iconButton:hover { border: 1px solid #00d4ff66; color: #00d4ff; }

QPushButton#quickAction {
    background-color: #0a121f;
    border: 1px solid #16334a;
    border-radius: 8px;
    color: #b8d4e6;
    font-size: 10px;
    font-weight: 600;
    padding: 10px;
    text-align: left;
}
QPushButton#quickAction:hover { border: 1px solid #00d4ff66; background-color: #0d1828; }

QPushButton#micPill {
    background-color: #00ff9518;
    border: 1px solid #00ff9555;
    border-radius: 20px;
    color: #00ff95;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 10px 28px;
}
QPushButton#micPillMuted {
    background-color: #ff335518;
    border: 1px solid #ff335555;
    border-radius: 20px;
    color: #ff3355;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 10px 28px;
}

QPushButton#navItem {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: #5a7a90;
}
QPushButton#navItem:hover { background: #0d1828; color: #00d4ff; }

QPushButton#engineRow {
    background: transparent;
    border: 1px solid #122638;
    border-radius: 6px;
    color: #5a7a90;
    font-size: 10px;
    font-weight: 600;
    text-align: left;
    padding: 9px 12px;
}
QPushButton#engineRowActive {
    background: #00d4ff14;
    border: 1px solid #00d4ff77;
    border-radius: 6px;
    color: #00d4ff;
    font-size: 10px;
    font-weight: 700;
    text-align: left;
    padding: 9px 12px;
}

QPushButton#outlineBtn {
    background: transparent;
    border: 1px solid #16334a;
    border-radius: 6px;
    color: #5a7a90;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
}
QPushButton#outlineBtn:hover { border: 1px solid #00d4ff66; color: #00d4ff; }

QPushButton#uploadZone {
    background-color: transparent;
    border: 1.5px dashed #16334a;
    border-radius: 10px;
    color: #3c5a70;
    font-size: 10px;
    padding: 14px;
}
QPushButton#uploadZone:hover {
    border: 1.5px dashed #00d4ff66;
    color: #00d4ff;
    background-color: #00d4ff08;
}

QPushButton#clearBtn {
    background: transparent;
    border: 1px solid #16334a;
    border-radius: 5px;
    color: #5a7a90;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1px;
}
QPushButton#clearBtn:hover { border: 1px solid #ff335566; color: #ff3355; }

/* ── Progress bars ── */
QProgressBar { background: #0d1f2e; border: none; border-radius: 3px; }
QProgressBar::chunk { border-radius: 3px; }

/* ── Tooltip ── */
QToolTip {
    background-color: #0a121f;
    border: 1px solid #16334a;
    color: #c5dce8;
    font-size: 10px;
    padding: 4px 8px;
}
"""