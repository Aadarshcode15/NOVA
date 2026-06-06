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

def main():
    # ── Logger must be first — everything after this is recorded ──
    from core.logger import log
    log.info("=" * 55)
    log.info("NOVA STARTING UP")
    log.info("=" * 55)

    # ── One-time memory migration (safe to run on every startup) ──
    from memory.memory_manager import load_memory, save_memory, migrate_v1_to_v2
    save_memory(migrate_v1_to_v2(load_memory()))

    # Register command callback
    set_command_callback(on_command)

    # Start always-on audio loop in background thread
    audio_thread = threading.Thread(target=audio_loop, daemon=True)
    audio_thread.start()

    # Launch PyQt6 UI (runs on main thread)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    from ui.main_window import NovaWindow
    window = NovaWindow()
    window.show()

    exit_code = app.exec()
    stop_audio_loop()

    # Print engine usage stats for this session
    from core.engine import log_engine_stats
    log_engine_stats()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
