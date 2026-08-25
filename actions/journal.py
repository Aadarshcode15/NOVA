# actions/journal.py
"""
Voice Journal.

Two ways to add entries:
  "Nova, add a voice note: I need to buy groceries"  → saves inline text
  "Nova, add a voice note"                           → records next spoken input

Reading:
  "Nova, read my journal"        → today's entries
  "Nova, what did I note today"  → same
  "Nova, what did I note yesterday" → yesterday's entries
"""
import re
from datetime import datetime, timedelta
from pathlib import Path
from config.settings import DATA_DIR
from core.logger import log
from core.voice  import speak
from core.engine import raw_query

JOURNAL_DIR = DATA_DIR / "journal"
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

# ── Recording state ────────────────────────────────────────────
# When True, the NEXT voice input becomes a journal entry
# instead of being routed as a command.
_awaiting_note: bool = False


def is_awaiting_note() -> bool:
    return _awaiting_note


def capture_and_save(transcribed_text: str) -> None:
    """Called by audio_loop when _awaiting_note is True."""
    global _awaiting_note
    _awaiting_note = False
    _write_entry(transcribed_text)
    speak("Voice note saved to your journal.")
    log.info(f"[Journal] Entry saved: '{transcribed_text[:60]}'")


# ── File helpers ───────────────────────────────────────────────

def _journal_path(date: datetime = None) -> Path:
    d = date or datetime.now()
    return JOURNAL_DIR / f"{d.strftime('%Y-%m-%d')}.md"


def _write_entry(text: str, date: datetime = None) -> None:
    path      = _journal_path(date)
    timestamp = datetime.now().strftime("%H:%M")

    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        d_str    = (date or datetime.now()).strftime("%A, %B %d %Y")
        existing = f"# Journal — {d_str}\n\n"

    entry = f"**[{timestamp}]** {text}\n\n"
    path.write_text(existing + entry, encoding="utf-8")


def _read_entries(date: datetime = None) -> str:
    path = _journal_path(date)
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    # Strip markdown formatting for speech
    content = re.sub(r"#+ ", "", content)
    content = re.sub(r"\*\*\[[\d:]+\]\*\* ", "", content)
    return content.strip()


def _count_entries(date: datetime = None) -> int:
    path = _journal_path(date)
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    return content.count("**[")


# ── Triggers ───────────────────────────────────────────────────

TRIGGERS = (
    "voice note", "journal", "add a note", "add note",
    "record a note", "start a note", "new note",
    "read my journal", "what did i note", "journal entry",
    "open journal", "today's notes", "yesterday's notes",
)

_ADD_TRIGGERS = (
    "add a voice note", "add a note", "add note",
    "record a note", "start a note", "new note",
    "voice note", "add to journal", "journal entry",
    "start voice note",
)

_READ_TRIGGERS = (
    "read my journal", "what did i note", "read journal",
    "today's notes", "open journal", "show my journal",
    "read today's journal",
)

_YESTERDAY_TRIGGERS = (
    "yesterday", "yesterday's notes", "yesterday's journal",
)


def handle_journal(command: str) -> bool:
    global _awaiting_note

    c = command.lower().strip()

    if not any(t in c for t in TRIGGERS):
        return False

    # ── Read yesterday ──────────────────────────────────────────
    if any(t in c for t in _YESTERDAY_TRIGGERS):
        yesterday = datetime.now() - timedelta(days=1)
        entries   = _read_entries(yesterday)
        count     = _count_entries(yesterday)
        if not entries:
            speak(f"No journal entries from yesterday.")
            return True
        speak(f"Yesterday you noted {count} thing{'s' if count != 1 else ''}.")
        summary = raw_query(
            f"Summarize these journal entries briefly in 2-3 spoken sentences:\n\n{entries[:2000]}",
            system="Summarize personal journal entries for a voice assistant. Be natural."
        )
        speak(summary or entries[:300])
        return True

    # ── Read today ──────────────────────────────────────────────
    if any(t in c for t in _READ_TRIGGERS):
        entries = _read_entries()
        count   = _count_entries()
        if not entries:
            speak("No journal entries for today yet. Say 'add a voice note' to create one.")
            return True
        speak(f"You have {count} note{'s' if count != 1 else ''} today.")
        if count <= 3:
            # Read all entries for short journals
            clean = re.sub(r"\n{2,}", ". ", entries).strip()
            speak(clean[:600])
        else:
            # Summarize long journals
            summary = raw_query(
                f"Summarize these journal entries in 3 spoken sentences:\n\n{entries[:2000]}",
                system="Summarize personal journal notes for a voice assistant."
            )
            speak(summary or entries[:300])
        return True

    # ── Add with inline content ("add a note: buy milk") ────────
    if any(t in c for t in _ADD_TRIGGERS):
        # Extract inline content after colon or "that"
        inline = ""
        for sep in [":", " that ", " saying ", " to say "]:
            if sep in command:
                inline = command.split(sep, 1)[1].strip()
                break

        # Remove trigger words to get remaining text
        if not inline:
            remaining = c
            for trigger in sorted(_ADD_TRIGGERS, key=len, reverse=True):
                remaining = remaining.replace(trigger, "").strip()
            remaining = remaining.strip(".,!?:- ")
            if len(remaining) > 5:
                inline = remaining

        if inline:
            # Inline note — save immediately
            _write_entry(inline)
            speak(f"Noted: {inline}")
        else:
            # No content — wait for next voice input
            _awaiting_note = True
            speak("Recording. Say your note now.")

        return True

    return False