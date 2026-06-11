# ui/tray.py
import threading
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui     import QIcon, QPixmap, QColor, QPainter, QFont, QAction
from PyQt6.QtCore    import Qt
from core.logger     import log


def _make_icon(color: str = "#00c8ff") -> QIcon:
    """
    Generate a tray icon programmatically — no image file required.
    Filled circle with the letter N centred.
    """
    size    = 64
    pixmap  = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Filled circle
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # "N" letter
    painter.setPen(QColor("white"))
    font = QFont("Arial", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
    painter.end()

    return QIcon(pixmap)


class NovaTray:
    """
    System tray icon for NOVA.
    - Single-click: context menu
    - Double-click: toggle show/hide window
    - Closing the window minimises to tray instead of quitting
    """

    ICON_ACTIVE = "#00c8ff"   # cyan  — normal
    ICON_MUTED  = "#ff3355"   # red   — microphone muted
    ICON_SPEAK  = "#00ff88"   # green — NOVA is speaking

    def __init__(self, window):
        self.window  = window
        self._muted  = False

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(_make_icon(self.ICON_ACTIVE))
        self.tray.setToolTip("N.O.V.A — Neural Operative Virtual Assistant\nDouble-click to show/hide")

        self._build_menu()
        self.tray.activated.connect(self._on_activate)
        self.tray.show()

        log.info("[Tray] System tray icon active.")

    def _build_menu(self) -> None:
        menu = QMenu()

        # Show / Hide
        self._show_action = QAction("◉  Show NOVA")
        self._show_action.triggered.connect(self._toggle_window)
        menu.addAction(self._show_action)

        menu.addSeparator()

        # Microphone toggle
        self._mic_action = QAction("🎤  Microphone: Active")
        self._mic_action.triggered.connect(self._toggle_mic)
        menu.addAction(self._mic_action)

        # Manual briefing trigger
        briefing_action = QAction("☀  Run Morning Briefing Now")
        briefing_action.triggered.connect(self._run_briefing)
        menu.addAction(briefing_action)

        menu.addSeparator()

        # Quit
        quit_action = QAction("✕  Quit NOVA")
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    # ── Slot handlers ──────────────────────────────────────

    def _on_activate(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Double-click toggles window visibility."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()

    def _toggle_window(self) -> None:
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
            self.tray.setToolTip("N.O.V.A — Microphone muted")
        else:
            self._mic_action.setText("🎤  Microphone: Active")
            self.tray.setIcon(_make_icon(self.ICON_ACTIVE))
            self.tray.setToolTip("N.O.V.A — Neural Operative Virtual Assistant")

    def _run_briefing(self) -> None:
        threading.Thread(
            target = _briefing_thread,
            daemon = True
        ).start()

    def _quit(self) -> None:
        log.info("[Tray] Quit requested from tray.")
        QApplication.instance().quit()

    # ── Public helpers ─────────────────────────────────────

    def notify(self, title: str, message: str, duration_ms: int = 3000) -> None:
        """Show a Windows system notification balloon from the tray."""
        self.tray.showMessage(
            title, message,
            QSystemTrayIcon.MessageIcon.Information,
            duration_ms
        )

    def set_speaking(self, is_speaking: bool) -> None:
        """Change icon colour when NOVA is speaking (optional visual feedback)."""
        if self._muted:
            return
        color = self.ICON_SPEAK if is_speaking else self.ICON_ACTIVE
        self.tray.setIcon(_make_icon(color))


def _briefing_thread() -> None:
    try:
        from memory.proactive import morning_briefing
        morning_briefing()
    except Exception as e:
        log.error(f"[Tray] Briefing failed: {e}")