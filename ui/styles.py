# ui/styles.py
MAIN_STYLESHEET = """
* {
    font-family: 'Courier New', 'Consolas', monospace;
    color: #a0cfe0;
    selection-background-color: #00c8ff33;
}
QMainWindow, QWidget#centralWidget {
    background-color: #060c14;
}
QWidget { background-color: transparent; }

/* ── Panels ── */
QWidget#leftPanel {
    background-color: #08111c;
    border-right: 1px solid #00c8ff33;
}
QWidget#rightPanel {
    background-color: #08111c;
    border-left: 1px solid #00c8ff33;
}
QWidget#centerPanel { background-color: #060c14; }
QWidget#topBar {
    background-color: #050a10;
    border-bottom: 1px solid #00c8ff44;
}
QWidget#bottomBar {
    background-color: #050a10;
    border-top: 1px solid #00c8ff22;
}

/* ── Labels ── */
QLabel#titleLabel {
    color: #00c8ff;
    font-size: 22px;
    font-weight: bold;
    letter-spacing: 8px;
}
QLabel#subtitleLabel {
    color: #1a4a5e;
    font-size: 9px;
    letter-spacing: 4px;
}
QLabel#clockLabel {
    color: #00c8ff;
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 2px;
}
QLabel#dateLabel {
    color: #1a4a5e;
    font-size: 9px;
    letter-spacing: 2px;
}
QLabel#assistantLabel {
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 2px;
}
QLabel#stateLabel {
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 2px;
}

/* ── Log ── */
QTextEdit#logWidget {
    background-color: #040810;
    border: 1px solid #00c8ff33;
    color: #a0cfe0;
    font-size: 11px;
    padding: 8px;
}
QScrollBar:vertical {
    background: #08111c; width: 5px; border: none;
}
QScrollBar::handle:vertical {
    background: #1a3a50; border-radius: 2px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #00c8ff55; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

/* ── Input ── */
QLineEdit#commandInput {
    background-color: #040810;
    border: 1px solid #00c8ff33;
    color: #a0cfe0;
    font-size: 11px;
    padding: 7px 10px;
}
QLineEdit#commandInput:focus {
    border: 1px solid #00c8ff77;
    color: #ffffff;
}
QLineEdit#commandInput::placeholder { color: #1a3a50; }

/* ── Buttons ── */
QPushButton#sendButton {
    background-color: #00c8ff22;
    border: 1px solid #00c8ff66;
    color: #00c8ff;
    font-size: 12px;
    font-weight: bold;
    padding: 7px 12px;
}
QPushButton#sendButton:hover {
    background-color: #00c8ff44;
    border: 1px solid #00c8ff;
}

QPushButton#uploadButton {
    background-color: transparent;
    border: 1px dashed #1a3a50;
    color: #1a3a50;
    font-size: 9px;
    padding: 10px;
    letter-spacing: 1px;
}
QPushButton#uploadButton:hover {
    border: 1px dashed #00c8ff66;
    color: #00c8ff;
    background-color: #00c8ff0a;
}

/* ── Tooltip ── */
QToolTip {
    background-color: #08111c;
    border: 1px solid #1a3a50;
    color: #a0cfe0;
    font-size: 10px;
    padding: 4px 8px;
}
"""
