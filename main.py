# main.py — N.O.V.A Entry Point
import sys
import threading
from PyQt6.QtWidgets import QApplication
from core.voice import audio_loop, set_command_callback, stop_audio_loop
from core.command_router import route

def on_command(assistant: str, command: str) -> None:
    """Called by voice loop when a command is recognized."""
    route(assistant, command)

def main():
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
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
