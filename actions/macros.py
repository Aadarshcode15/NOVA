# actions/macros.py
"""
Command Macros / Routines.

Record a sequence of commands once, replay with one phrase.

Usage:
  "Nova, record morning routine"   → starts recording
  "Nova, what is the weather"      → captured (NOT executed)
  "Nova, check my calendar"        → captured
  "Nova, stop recording"           → saved

  "Nova, run morning routine"      → executes all 3
  "Nova, list my routines"         → lists saved routines
  "Nova, delete morning routine"   → deletes it
"""
import json
import time
import threading
from pathlib import Path
from config.settings import DATA_DIR
from core.logger import log
from core.voice  import speak

MACROS_FILE = DATA_DIR / "macros.json"

# ── Recording state ────────────────────────────────────────────
_recording:          bool  = False
_recording_name:     str   = ""
_recorded_commands:  list  = []


def is_recording() -> bool:
    return _recording

def get_recording_name() -> str:
    return _recording_name

def capture_command(command: str) -> None:
    """Add a command to the current recording. Called from router."""
    _recorded_commands.append(command)
    count = len(_recorded_commands)
    speak(f"Got it. Step {count} recorded. Say another command or 'stop recording' when done.")
    log.info(f"[Macro] Captured step {count}: '{command}'")


# ── Storage ────────────────────────────────────────────────────

def _load() -> dict:
    try:
        if MACROS_FILE.exists():
            return json.loads(MACROS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save(macros: dict) -> None:
    try:
        MACROS_FILE.parent.mkdir(parents=True, exist_ok=True)
        MACROS_FILE.write_text(json.dumps(macros, indent=2), encoding="utf-8")
    except Exception as e:
        log.error(f"[Macro] Save error: {e}")


# ── Triggers ───────────────────────────────────────────────────

TRIGGERS = (
    "record", "save this as", "stop recording", "done recording",
    "run ", "play ", "execute ", "start ",
    "list my routines", "list routines", "list my macros", "show routines",
    "delete routine", "delete macro", "remove routine",
)

_RECORD_START  = ("record", "save this as", "start recording")
_RECORD_STOP   = ("stop recording", "done recording", "finish recording", "save routine")
_RUN           = ("run ", "play ", "execute ", "start ")
_LIST          = ("list my routines", "list routines", "list my macros", "show routines",
                  "what routines", "what macros")
_DELETE        = ("delete routine", "delete macro", "remove routine", "remove macro")

def _extract_name(command: str, prefixes: tuple) -> str:
    """Extract routine name by stripping trigger prefixes."""
    c = command.lower().strip()
    for prefix in sorted(prefixes, key=len, reverse=True):
        if c.startswith(prefix):
            name = c[len(prefix):].strip().strip(".,!?")
            return name
    return c.strip()


def handle_macro(command: str) -> bool:
    global _recording, _recording_name, _recorded_commands

    c = command.lower().strip()

    # ── Stop recording ──────────────────────────────────────────
    if any(t in c for t in _RECORD_STOP):
        if not _recording:
            return False
        if not _recorded_commands:
            speak("No commands were recorded. Try again.")
            _recording = False
            return True
        macros = _load()
        macros[_recording_name] = _recorded_commands.copy()
        _save(macros)
        count = len(_recorded_commands)
        name  = _recording_name
        _recording         = False
        _recording_name    = ""
        _recorded_commands = []
        speak(
            f"Routine '{name}' saved with {count} "
            f"step{'s' if count != 1 else ''}. "
            f"Say 'run {name}' to use it anytime."
        )
        return True

    # ── Start recording ─────────────────────────────────────────
    if any(t in c for t in _RECORD_START) and not _recording:
        name = _extract_name(command, _RECORD_START)
        if not name:
            speak("What should I name this routine? For example: record morning routine.")
            return True
        _recording         = True
        _recording_name    = name
        _recorded_commands = []
        speak(
            f"Recording '{name}'. "
            f"Say your commands one by one. "
            f"Say 'stop recording' when done."
        )
        log.info(f"[Macro] Recording started: '{name}'")
        return True

    # ── Run routine ─────────────────────────────────────────────
    if any(t in c for t in ("run ", "play ", "execute ")):
        name   = _extract_name(command, ("run ", "play ", "execute ", "start "))
        macros = _load()

        # Fuzzy match: find closest routine name
        match = None
        if name in macros:
            match = name
        else:
            for key in macros:
                if name in key or key in name:
                    match = key
                    break

        if not match:
            available = ", ".join(macros.keys()) if macros else "none saved yet"
            speak(
                f"I don't have a routine called '{name}'. "
                f"Available routines: {available}."
            )
            return True

        commands = macros[match]
        count    = len(commands)
        speak(f"Running '{match}' — {count} step{'s' if count != 1 else ''}.")
        log.info(f"[Macro] Running '{match}': {commands}")

        def _execute_sequence():
            from core.command_router import route
            from core.engine import get_assistant
            asst = get_assistant()
            for i, cmd in enumerate(commands, 1):
                log.info(f"[Macro] Step {i}/{count}: '{cmd}'")
                try:
                    route(asst, cmd)
                    time.sleep(0.8)   # brief gap between commands
                except Exception as e:
                    log.error(f"[Macro] Step {i} failed: {e}")
                    speak(f"Step {i} failed. Continuing.")

        threading.Thread(target=_execute_sequence, daemon=True, name="MacroRunner").start()
        return True

    # ── List routines ───────────────────────────────────────────
    if any(t in c for t in _LIST):
        macros = _load()
        if not macros:
            speak("You have no saved routines. Say 'record' followed by a name to create one.")
            return True
        names = list(macros.keys())
        speak(f"You have {len(names)} routine{'s' if len(names) != 1 else ''}: "
              f"{', '.join(names)}.")
        return True

    # ── Delete routine ──────────────────────────────────────────
    if any(t in c for t in _DELETE):
        name   = _extract_name(command, _DELETE)
        macros = _load()
        if name not in macros:
            speak(f"I don't have a routine called '{name}'.")
            return True
        del macros[name]
        _save(macros)
        speak(f"Routine '{name}' deleted.")
        return True

    return False