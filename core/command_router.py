# core/command_router.py
from core.voice  import speak, speak_nova, speak_sora
from core.engine import query, set_engine, get_engine, Engine

# ── Lazy imports (only load when needed) ──────────────────
def _sys():
    from actions.system_control import handle_system
    return handle_system

def _spotify():
    from actions.spotify import handle_spotify
    return handle_spotify

def _whatsapp():
    from actions.whatsapp import handle_whatsapp
    return handle_whatsapp

def _weather_news():
    from actions.weather_news import handle_weather, handle_news_command
    return handle_weather, handle_news_command

def _reminder():
    from actions.reminder import handle_reminder
    return handle_reminder

def _todo():
    from actions.todo import handle_todo
    return handle_todo

def _memory():
    from actions.memory_handler import handle_memory
    return handle_memory

def _vision():
    from actions.screen_vision import handle_vision
    return handle_vision

def _youtube():
    from actions.youtube import handle_youtube
    return handle_youtube

def _files():
    from actions.file_manager import handle_files
    return handle_files

def _code():
    from actions.code_helper import handle_code
    return handle_code

def _desktop():
    from actions.desktop import handle_desktop
    return handle_desktop

def _search():
    from actions.web_search import handle_search
    return handle_search

# ── Engine switch commands ─────────────────────────────────
def _handle_engine_switch(command: str) -> bool:
    c = command.lower()
    if "switch to gemini" in c or "use gemini" in c:
        set_engine(Engine.GEMINI)
        speak("Switched to Gemini.")
        return True
    if "switch to groq" in c or "use groq" in c:
        set_engine(Engine.GROQ)
        speak("Switched to Groq.")
        return True
    if "switch to ollama" in c or "use ollama" in c or "go offline" in c:
        set_engine(Engine.OLLAMA)
        speak("Switched to Ollama. Running locally now.")
        return True
    return False

# ── Exit ──────────────────────────────────────────────────
def _handle_exit(command: str) -> bool:
    if any(k in command for k in ("shut down", "shutdown", "exit nova", "goodbye nova", "stop nova")):
        speak("Signing off. Have a great day.")
        raise SystemExit
    return False

# ── Time / Date ────────────────────────────────────────────
def _handle_time_date(command: str) -> bool:
    import datetime
    now = datetime.datetime.now()
    if "time" in command:
        speak(f"It is {now.strftime('%I:%M %p')}.")
        return True
    if "date" in command:
        speak(f"Today is {now.strftime('%A, %B %d, %Y')}.")
        return True
    return False

# ── Main Router ───────────────────────────────────────────
def route(assistant: str, command: str) -> None:
    """
    Routes a command to the correct action handler.
    Falls back to AI query if no handler matches.
    """
    c = command.lower().strip()
    print(f"[Router] {assistant.upper()} → {c}")

    try:
        if _handle_exit(c):              return
        if _handle_engine_switch(c):     return
        if _handle_time_date(c):         return

        # ── Handlers that need ORIGINAL casing (proper nouns, names, paths) ──
        if _memory()(command):           return   # "Remember my friend Priya"
        if _whatsapp()(command):         return   # contact name lookup
        if _reminder()(command):         return   # time expressions
        if _code()(command):             return   # file names on desktop
        if _files()(command):            return   # file/folder names

        # ── Handlers fine with lowercase ──
        if _sys()(c):                    return
        if _spotify()(c):                return
        if _todo()(c):                   return

        handle_weather, handle_news = _weather_news()
        if handle_weather(c):            return
        if handle_news(c):               return

        if _vision()(c):                 return
        if _youtube()(c):                return
        if _desktop()(c):                return
        if _search()(c):                 return

        # ── AI Fallback — always use original command ──
        response = query(command, assistant)
        speak(response, assistant)

    except Exception as e:
        import traceback
        print(f"[Router Error] {e}")
        traceback.print_exc()
        speak("Something went wrong. Please try again.")
