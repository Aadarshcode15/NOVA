# main.py — N.O.V.A Entry Point
import os
import sys
import warnings
import threading

# ── Suppress third-party warnings ─────────────────────────
# Must be set before any imports that trigger them

# Qt font warnings for non-Latin scripts
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false"

# faster-whisper: Windows symlinks not supported — cache still works fine
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# HuggingFace unauthenticated request warning — free tier is fine for local models
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

# HuggingFace tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# pygame pkg_resources deprecation
warnings.filterwarnings("ignore", message=".*pkg_resources.*")
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")

# HuggingFace hub warnings
warnings.filterwarnings("ignore", message=".*huggingface_hub.*")
warnings.filterwarnings("ignore", message=".*symlinks.*")
warnings.filterwarnings("ignore", message=".*unauthenticated.*")

# Suppress Qt font warnings for Devanagari/CJK scripts
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false"

from PyQt6.QtWidgets import QApplication
from core.voice import audio_loop, set_command_callback, stop_audio_loop
from core.command_router import route

def on_command(assistant: str, command: str) -> None:
    """Called by voice loop when a command is recognized."""
    route(assistant, command)

# REPLACE WITH:
def main():
    # ── Logger must be first ──
    from core.logger import log
    log.info("=" * 55)
    log.info("NOVA STARTING UP")
    log.info("=" * 55)

    # ── One-time memory migration ──
    from memory.memory_manager import load_memory, save_memory, migrate_v1_to_v2
    save_memory(migrate_v1_to_v2(load_memory()))

    # ── Apply user settings ──
    from config.user_config import apply_all
    apply_all()
    log.info("[Config] User settings applied.")

    # ── Initialise conversation history database ──
    from core.conversation_log import init_db
    init_db()

    # ── Start proactive system alerts ──
    from core.alerts import start_alerts
    start_alerts()
    log.info("[Alerts] System monitor active.")

    # ── Build behavioral brain context from history ──
    # Runs in background so startup isn't delayed
    import threading as _t
    _t.Thread(
        target=lambda: __import__('core.brain', fromlist=['build_behavioral_context'])
                       .build_behavioral_context(),
        daemon=True, name="Brain-Builder"
    ).start()

    # ── Start proactive briefing scheduler ──
    from memory.proactive import start_briefing_scheduler
    start_briefing_scheduler()

    # Register command callback
    set_command_callback(on_command)

    # Start always-on audio loop in background thread
    audio_thread = threading.Thread(target=audio_loop, daemon=True)
    audio_thread.start()

    # Launch PyQt6 UI (runs on main thread)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)   # keep alive when window is hidden

    from ui.main_window import NovaWindow
    window = NovaWindow()

    # ── System tray ──
    from ui.tray import NovaTray
    tray = NovaTray(window)
    window._tray = tray    # give window a reference for closeEvent

    window.show()

    exit_code = app.exec()
    stop_audio_loop()

    from core.engine import log_engine_stats
    log_engine_stats()

    from core.perf import log_session_stats
    log_session_stats()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
