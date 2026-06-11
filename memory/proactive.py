# memory/proactive.py
import time
import threading
import schedule
from datetime import datetime
from core.logger import log


# ── Briefing sections (toggle each on/off) ─────────────────
BRIEFING_CONFIG = {
    "greeting":  True,
    "date":      True,
    "weather":   True,
    "calendar":  True,
    "todo":      True,
    "news":      False,   # off by default — too long for daily spoken briefing
}


def _get_user_name() -> str:
    """Pull user's first name from long-term memory."""
    try:
        from memory.memory_manager import load_memory
        memory   = load_memory()
        identity = memory.get("identity", {})
        for key, entry in identity.items():
            val = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            # "my name is Raj" → "Raj"
            words = val.lower().split()
            if "name" in words and len(words) >= 3:
                return val.split()[-1].capitalize()
            if "name" in key.lower():
                return val.split()[-1].capitalize()
    except Exception:
        pass
    return ""


def morning_briefing() -> None:
    """
    Delivers a spoken morning briefing via NOVA.
    Can be triggered automatically (scheduler) or manually by voice.
    Each section queues to the async TTS worker — no blocking.
    """
    from core.voice import speak

    log.info("[Briefing] Starting morning briefing...")

    # ── 1. Greeting ─────────────────────────────────────
    if BRIEFING_CONFIG["greeting"]:
        hour = datetime.now().hour
        if hour < 12:   prefix = "Good morning"
        elif hour < 17: prefix = "Good afternoon"
        else:           prefix = "Good evening"

        name = _get_user_name()
        intro = f"{prefix}, {name}!" if name else f"{prefix}!"
        speak(f"{intro} Here is your daily briefing.")
        time.sleep(0.3)   # let TTS queue settle between sections

    # ── 2. Date ──────────────────────────────────────────
    if BRIEFING_CONFIG["date"]:
        today = datetime.now().strftime("%A, %B %d")
        speak(f"Today is {today}.")
        time.sleep(0.2)

    # ── 3. Weather ───────────────────────────────────────
    if BRIEFING_CONFIG["weather"]:
        try:
            from actions.weather_news import handle_weather
            handle_weather("weather")
            time.sleep(0.2)
        except Exception as e:
            log.error(f"[Briefing] Weather section failed: {e}")

    # ── 4. Calendar ──────────────────────────────────────
    if BRIEFING_CONFIG["calendar"]:
        try:
            from actions.calendar import handle_calendar
            handle_calendar("what's on my calendar today")
            time.sleep(0.2)
        except Exception as e:
            log.warning(f"[Briefing] Calendar section skipped: {e}")

    # ── 5. Todo list ─────────────────────────────────────
    if BRIEFING_CONFIG["todo"]:
        try:
            from actions.todo import _load as load_todos
            todos = load_todos()
            if todos:
                count = len(todos)
                speak(f"You have {count} item{'s' if count > 1 else ''} on your to-do list.")
                for i, item in enumerate(todos[:3], 1):
                    speak(f"{i}. {item}")
                if count > 3:
                    speak(f"And {count - 3} more.")
            else:
                speak("Your to-do list is clear.")
            time.sleep(0.2)
        except Exception as e:
            log.error(f"[Briefing] Todo section failed: {e}")

    # ── 6. News (optional) ───────────────────────────────
    if BRIEFING_CONFIG["news"]:
        try:
            from actions.weather_news import _fetch_news
            _fetch_news("general")
            time.sleep(0.2)
        except Exception as e:
            log.error(f"[Briefing] News section failed: {e}")

    # ── Close ────────────────────────────────────────────
    speak("That is your briefing. Have a productive day!")
    log.info("[Briefing] Morning briefing complete.")


# ── Scheduler ──────────────────────────────────────────────

def _scheduler_loop() -> None:
    from config.settings import MORNING_BRIEFING_TIME
    schedule.every().day.at(MORNING_BRIEFING_TIME).do(morning_briefing)
    log.info(f"[Briefing] Scheduled daily at {MORNING_BRIEFING_TIME}")

    while True:
        schedule.run_pending()
        time.sleep(30)   # check every 30 seconds — lightweight


def start_briefing_scheduler() -> None:
    """Start the background scheduler. Call once at startup."""
    thread = threading.Thread(
        target = _scheduler_loop,
        daemon = True,
        name   = "Briefing-Scheduler"
    )
    thread.start()
    log.info("[Briefing] Scheduler started.")