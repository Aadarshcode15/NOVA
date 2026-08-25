# actions/clipboard_assistant.py
"""
Smart Clipboard Assistant — activates ONLY on explicit request.
No background polling, no automatic triggers.

Trigger: "see the clipboard" / "what did I copy" / "smart clipboard"
"""
import re
import pyperclip
from core.logger import log
from core.voice  import speak
from core.engine import raw_query

import time as _time

# ── Session state ──────────────────────────────────────────────
_clipboard_content:       str   = ""
_clipboard_type:          str   = ""
_clipboard_last_accessed: float = 0.0        # timestamp of last clipboard trigger
_CLIPBOARD_SESSION_SECS:  float = 120.0      # 2-minute session window

def get_clipboard_context() -> tuple:
    return _clipboard_content, _clipboard_type

def clipboard_session_active() -> bool:
    """Returns True if clipboard was accessed within the last 2 minutes."""
    return (
        bool(_clipboard_content) and
        _time.time() - _clipboard_last_accessed < _CLIPBOARD_SESSION_SECS
    )


# ── Content type detection ─────────────────────────────────────

def _detect_type(text: str) -> str:
    t = text.strip()
    if re.match(r'https?://', t):
        if "youtube.com" in t or "youtu.be" in t:
            return "youtube_url"
        return "url"
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', t):
        return "email"
    if re.match(r'^[\d\+\-\(\) ]{7,15}$', t.replace(" ", "")):
        return "phone"
    code_signals = (
        "def ", "class ", "import ", "function ", "const ", "var ", "let ",
        "<html", "<div", "SELECT ", "INSERT ", "CREATE TABLE", "#!/",
        "public class", "print(", "console.log",
    )
    if any(sig in t for sig in code_signals):
        return "code"
    if len(t.split()) > 30:
        return "long_text"
    if len(t.split()) > 5:
        return "short_text"
    return "snippet"


def _handle_follow_up(command: str) -> bool:
    """
    Handle follow-up commands after clipboard was analyzed.
    Returns True if handled.
    """
    global _clipboard_content, _clipboard_type

    if not _clipboard_content:
        return False

    c = command.lower().strip()

    # ── URL follow-ups ──
    if _clipboard_type in ("url", "youtube_url"):
        if "open it" in c or "open the link" in c:
            import webbrowser
            webbrowser.open(_clipboard_content.strip())
            speak("Opening the link.")
            return True
        if "summarize" in c or "summary" in c:
            if _clipboard_type == "youtube_url":
                from actions.youtube import _extract_video_id, _summarize_content
                vid = _extract_video_id(_clipboard_content)
                if vid:
                    speak("Summarizing the YouTube video.")
                    speak(_summarize_content(vid, brief=True))
                    return True
            else:
                speak("Fetching the page content.")
                try:
                    import requests
                    r    = requests.get(_clipboard_content, timeout=8)
                    from html.parser import HTMLParser
                    class _S(HTMLParser):
                        parts = []
                        def handle_data(self, d): self.parts.append(d)
                    s = _S(); s.feed(r.text)
                    page_text = " ".join(s.parts)[:3000]
                    summary   = raw_query(
                        f"Summarize this web page in 3 spoken sentences:\n{page_text}",
                        system="Summarize web content for a voice assistant. No markdown."
                    )
                    speak(summary or "Could not summarize this page.")
                except Exception as e:
                    speak("Could not fetch that page right now.")
                return True

    # ── Code follow-ups ──
    if _clipboard_type == "code":
        if "explain" in c:
            explanation = raw_query(
                f"Explain this code in 3 spoken sentences. No markdown:\n\n{_clipboard_content[:2000]}",
                system="You explain code for a voice assistant. Be concise."
            )
            speak(explanation or "Could not explain the code.")
            return True
        if "fix" in c or "debug" in c:
            fixed = raw_query(
                f"Fix ALL bugs in this code. Return ONLY fixed code:\n\n{_clipboard_content}"
            )
            if fixed:
                import pyperclip as pc
                pc.copy(fixed)
                speak("Fixed code copied to clipboard.")
            return True
        if "save it" in c:
            from actions.code_helper import CODE_DIR, _detect_language, _sanitize_name
            import sys
            from datetime import datetime
            ext, lang, _ = _detect_language(_clipboard_content)
            fname        = f"clipboard_{datetime.now().strftime('%H%M%S')}{ext}"
            fpath        = CODE_DIR / fname
            fpath.write_text(_clipboard_content, encoding="utf-8")
            speak(f"Saved to Nova Code Helper as {fname}.")
            return True

    # ── Text follow-ups ──
    if _clipboard_type in ("long_text", "short_text"):
        if "summarize" in c or "summary" in c:
            summary = raw_query(
                f"Summarize this text in 2-3 spoken sentences. No markdown:\n\n{_clipboard_content[:3000]}",
                system="Summarize text for a voice assistant. No formatting."
            )
            speak(summary or "Could not summarize.")
            return True
        if "read" in c or "read it" in c:
            snippet = _clipboard_content[:300].replace("\n", " ")
            speak(snippet)
            return True
        if "translate" in c:
            lang    = "Hindi" if "hindi" in c else "English"
            result  = raw_query(
                f"Translate this text to {lang} in spoken Roman script. No markdown:\n\n{_clipboard_content[:1000]}",
                system="You translate text for a voice assistant."
            )
            speak(result or "Could not translate.")
            return True

    # ── Email follow-ups ──
    if _clipboard_type == "email":
        if "send" in c or "email" in c or "compose" in c:
            speak(f"Composing email to {_clipboard_content.strip()}.")
            # Route to email handler
            from actions.email import _get_gmail_service, _send_email
            return True

    return False


# ── Triggers ───────────────────────────────────────────────────

TRIGGERS = (
    "see the clipboard", "check clipboard", "read my clipboard",
    "what did i copy", "what's in my clipboard", "what is in my clipboard",
    "smart clipboard", "clipboard assistant", "analyze clipboard",
    "what have i copied", "clipboard", "show clipboard",
)


# REPLACE:
def handle_clipboard(command: str) -> bool:
    global _clipboard_content, _clipboard_type, _clipboard_last_accessed

    c = command.lower().strip()

    # ── Follow-up within active session window ──────────────────
    # Only handles follow-ups (read it / summarize it / open it etc.)
    # if clipboard was accessed within the last 2 minutes.
    # This prevents clipboard from stealing "summarize it" commands
    # that belong to a recently uploaded file.
    if clipboard_session_active() and _handle_follow_up(command):
        _clipboard_last_accessed = _time.time()   # keep session alive
        return True

    # ── Explicit clipboard activation trigger ───────────────────
    if not any(t in c for t in TRIGGERS):
        return False

    # ── Read clipboard ──────────────────────────────────────────
    try:
        content = pyperclip.paste()
    except Exception as e:
        log.error(f"[Clipboard] Read error: {e}")
        speak("I couldn't access the clipboard.")
        return True

    if not content or not content.strip():
        speak("Your clipboard is empty. Copy something first.")
        return True

    content = content.strip()
    _clipboard_content       = content
    _clipboard_type          = _detect_type(content)
    _clipboard_last_accessed = _time.time()    # ← start session timer

    # ── Read clipboard ──────────────────────────────────────────
    try:
        content = pyperclip.paste()
    except Exception as e:
        log.error(f"[Clipboard] Read error: {e}")
        speak("I couldn't access the clipboard.")
        return True

    if not content or not content.strip():
        speak("Your clipboard is empty. Copy something first.")
        return True

    content = content.strip()
    _clipboard_content = content
    _clipboard_type    = _detect_type(content)

    preview = content[:80].replace("\n", " ").strip()

    # ── Type-specific response ──────────────────────────────────
    if _clipboard_type == "youtube_url":
        speak(
            f"I see a YouTube link in your clipboard. "
            f"Say 'summarize it' to get a summary, or 'open it' to watch."
        )

    elif _clipboard_type == "url":
        speak(
            f"I see a web link: {preview}. "
            f"Say 'open it' to open it, or 'summarize it' to get a page summary."
        )

    elif _clipboard_type == "code":
        lines = content.count("\n") + 1
        speak(
            f"I see {lines} lines of code in your clipboard. "
            f"Say 'explain it', 'fix it', or 'save it' to Nova Code Helper."
        )

    elif _clipboard_type == "long_text":
        words = len(content.split())
        speak(
            f"I see a {words}-word text in your clipboard. "
            f"Say 'summarize it', 'read it', or 'translate it'."
        )

    elif _clipboard_type == "short_text":
        speak(
            f"Clipboard contains: {preview}. "
            f"Say 'summarize it', 'read it', or 'translate it'."
        )

    elif _clipboard_type == "email":
        speak(
            f"I see the email address {content.strip()}. "
            f"Say 'send an email to this' to compose a message."
        )

    elif _clipboard_type == "phone":
        speak(
            f"I see a phone number: {content.strip()}. "
            f"Say 'send a WhatsApp message to this number'."
        )

    else:
        speak(f"Clipboard contains: {preview}.")

    return True