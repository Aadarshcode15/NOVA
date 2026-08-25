# ui/tray.py
from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication,
    QFrame, QVBoxLayout, QLabel, QPushButton
)
from PyQt6.QtGui  import QIcon, QPixmap, QColor, QPainter, QFont, QAction, QCursor
from PyQt6.QtCore import Qt, QTimer, QPoint
from core.logger  import log


def _make_icon(color: str = "#00d4ff") -> QIcon:
    size   = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.setPen(QColor("white"))
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    painter.end()
    return QIcon(pixmap)


def _flyout_btn_style(color: str) -> str:
    return (
        f"QPushButton{{background:{color}14; border:1px solid {color}55; border-radius:5px;"
        f"color:{color}; font-size:10px; font-weight:700; padding:6px 10px; text-align:left;}}"
        f"QPushButton:hover{{background:{color}28;}}"
    )


class _HoverFlyout(QFrame):
    """Small frameless popup shown when hovering the tray icon."""

    def __init__(self, owner):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self._owner = owner
        self.setStyleSheet("QFrame{background:#0a121f; border:1px solid #00d4ff55; border-radius:8px;}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10); lay.setSpacing(6)

        title = QLabel("N.O.V.A")
        title.setStyleSheet("color:#00d4ff; font-size:11px; font-weight:800; letter-spacing:2px;")
        lay.addWidget(title)

        show_btn = QPushButton("◉  Show Window")
        show_btn.setStyleSheet(_flyout_btn_style("#00d4ff"))
        show_btn.clicked.connect(self._owner._toggle_window)
        lay.addWidget(show_btn)

        quit_btn = QPushButton("✕  Close NOVA")
        quit_btn.setStyleSheet(_flyout_btn_style("#ff3355"))
        quit_btn.clicked.connect(self._owner._quit)
        lay.addWidget(quit_btn)

        self.setFixedWidth(160)
        self.adjustSize()

    def enterEvent(self, event):
        self._owner._mouse_over_flyout = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._owner._mouse_over_flyout = False
        super().leaveEvent(event)


class NovaTray:
    ICON_ACTIVE = "#00d4ff"
    ICON_MUTED  = "#ff3355"
    ICON_SPEAK  = "#00ff95"

    def __init__(self, window):
        self.window = window
        self._muted = False
        self._mouse_over_flyout = False

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(_make_icon(self.ICON_ACTIVE))
        self.tray.setToolTip("N.O.V.A — Neural Operative Virtual Assistant")
        self._build_menu()
        self.tray.activated.connect(self._on_activate)
        self.tray.show()

        self._flyout = _HoverFlyout(self)
        self._flyout.hide()

        # Qt has no native tray-hover signal — poll cursor vs icon geometry instead.
        self._hover_timer = QTimer()
        self._hover_timer.timeout.connect(self._check_hover)
        self._hover_timer.start(200)

        log.info("[Tray] System tray icon active.")

    def _build_menu(self) -> None:
        menu = QMenu()
        self._show_action = QAction("◉  Show NOVA")
        self._show_action.triggered.connect(self._toggle_window)
        menu.addAction(self._show_action)
        menu.addSeparator()
        self._mic_action = QAction("🎤  Microphone: Active")
        self._mic_action.triggered.connect(self._toggle_mic)
        menu.addAction(self._mic_action)
        briefing_action = QAction("☀  Run Morning Briefing Now")
        briefing_action.triggered.connect(self._run_briefing)
        menu.addAction(briefing_action)
        menu.addSeparator()
        quit_action = QAction("✕  Quit NOVA")
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)

    def _on_activate(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()

    def _check_hover(self) -> None:
        try:
            tray_rect = self.tray.geometry()
            if tray_rect.isNull():
                return
            margin   = 6
            expanded = tray_rect.adjusted(-margin, -margin, margin, margin)
            over_icon = expanded.contains(QCursor.pos())

            if over_icon and not self._flyout.isVisible():
                x = tray_rect.center().x() - self._flyout.width() // 2
                y = tray_rect.top() - self._flyout.height() - 8
                self._flyout.move(QPoint(x, y))
                self._flyout.show()
            elif not over_icon and not self._mouse_over_flyout and self._flyout.isVisible():
                self._flyout.hide()
        except Exception:
            pass

    def _toggle_window(self) -> None:
        self._flyout.hide()
        if self.window.isVisible():
            self.window.hide()
            self._show_action.setText("◉  Show NOVA")
        else:
            self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()
            self._show_action.setText("◯  Hide NOVA")

    def _toggle_mic(self) -> None:
        self.window._on_mute()
        self._muted = not self._muted
        if self._muted:
            self._mic_action.setText("🔇  Microphone: Muted")
            self.tray.setIcon(_make_icon(self.ICON_MUTED))
        else:
            self._mic_action.setText("🎤  Microphone: Active")
            self.tray.setIcon(_make_icon(self.ICON_ACTIVE))

    def _run_briefing(self) -> None:
        import threading
        threading.Thread(target=self._briefing_thread, daemon=True).start()

    def _briefing_thread(self) -> None:
        try:
            from memory.proactive import morning_briefing
            morning_briefing()
        except Exception as e:
            log.error(f"[Tray] Briefing failed: {e}")

    def _quit(self) -> None:
        self._flyout.hide()
        log.info("[Tray] Quit requested.")
        QApplication.instance().quit()

    def notify(self, title: str, message: str, duration_ms: int = 3000) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms)

    def set_speaking(self, is_speaking: bool) -> None:
        if self._muted:
            return
        color = self.ICON_SPEAK if is_speaking else self.ICON_ACTIVE
        self.tray.setIcon(_make_icon(color))