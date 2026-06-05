# actions/reminder.py
import re
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from core.voice import speak
from config.settings import REMINDER_DIR
from core.logger import log

def _sanitise(text: str) -> str:
    return (
        text.replace("\\", "").replace('"', "")
            .replace("'", "").replace("\n", " ").strip()
    )[:200]

def _parse(command: str):
    """Returns (message, datetime) or (None, None)."""
    c   = command.lower().strip()
    now = datetime.now()

    for filler in sorted([
        "please remind me to", "remind me to", "set a reminder to",
        "set a reminder for", "set reminder to", "set reminder for",
        "reminder to", "reminder for", "reminder at", "reminder",
        "remind me", "nova", "sora"
    ], key=len, reverse=True):
        c = c.replace(filler, "")
    c = c.strip()

    dt = None

    # ── "in X minutes/hours" ──
    m = re.search(r"in\s+(\d+)\s+(minute|minutes|min|hour|hours|hr)", c)
    if m:
        amount = int(m.group(1))
        unit   = m.group(2)
        dt     = now + (timedelta(hours=amount) if "hour" in unit or "hr" in unit
                        else timedelta(minutes=amount))
        msg = re.sub(r"in\s+\d+\s+\w+", "", c).strip().strip(".,!?")
        return msg or "Reminder", dt

    # ── "at H:MM am/pm" ──
    m = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", c)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm   = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if dt <= now:
            dt += timedelta(days=1)
        if "tomorrow" in c:
            dt += timedelta(days=1)
        time_str = m.group(0)
        msg      = c.replace(time_str, "").replace("tomorrow", "").replace("today", "").strip().strip(".,!?")
        return msg or "Reminder", dt

    return None, None

def _create_task(task_name: str, dt: datetime, message: str) -> bool:
    try:
        script_path = REMINDER_DIR / f"{task_name}.py"
        python_exe  = sys.executable
        script_code = f"""
import time
try:
    from win10toast import ToastNotifier
    t = ToastNotifier()
    t.show_toast("NOVA Reminder", "{_sanitise(message)}", duration=10, threaded=True)
    time.sleep(11)
except Exception as e:
    log.info(e)
try:
    import winsound
    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
except Exception:
    pass
"""
        script_path.write_text(script_code, encoding="utf-8")
        cmd = [
            "schtasks", "/create", "/f",
            "/tn", f"NOVA\\{task_name}",
            "/tr", f'"{python_exe}" "{script_path}"',
            "/sc", "once",
            "/st", dt.strftime("%H:%M"),
            "/sd", dt.strftime("%m/%d/%Y"),
            "/rl", "highest",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            log.error(f"[Reminder] schtasks error: {result.stderr}")
            return False
        log.info(f"[Reminder] Created: {task_name} at {dt}")
        return True
    except Exception as e:
        log.error(f"[Reminder] Error: {e}")
        return False

TRIGGERS = ("remind me", "set a reminder", "set reminder", "reminder")

def handle_reminder(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    msg, dt = _parse(command)

    if dt is None:
        speak(
            "I couldn't figure out the time for that reminder. "
            "Try saying something like — remind me to call mom at 6 PM, "
            "or remind me in 30 minutes."
        )
        return True

    task_name = f"reminder_{dt.strftime('%Y%m%d_%H%M%S')}"
    success   = _create_task(task_name, dt, msg or "Reminder")

    if success:
        time_fmt = dt.strftime("%I:%M %p")
        tomorrow = (datetime.now() + timedelta(days=1)).date()
        if dt.date() == tomorrow:
            speak(f"Got it. I will remind you to {msg} tomorrow at {time_fmt}.")
        else:
            speak(f"Got it. I will remind you to {msg} at {time_fmt}.")
    else:
        speak("Sorry, I couldn't create the reminder. Try running NOVA as administrator.")
    return True