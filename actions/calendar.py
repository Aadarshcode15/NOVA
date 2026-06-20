# actions/calendar.py
import re
from datetime import datetime, timedelta
from pathlib import Path
from actions.base_action import BaseAction, ActionResult, _AuthRequired
from config.settings import BASE_DIR
from core.logger import log

# ── Paths ──────────────────────────────────────────────────
CREDS_FILE = BASE_DIR / "config" / "credentials.json"
TOKEN_FILE  = BASE_DIR / "data"   / "token_calendar.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
TIMEZONE    = "Asia/Kolkata"


# ── Auth ───────────────────────────────────────────────────

def _get_service():
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not CREDS_FILE.exists():
        raise _AuthRequired(
            "Google credentials not found. "
            "Please download credentials.json from Google Cloud Console "
            "and place it in your config folder."
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Try to refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            # invalid_grant = token revoked or credentials replaced
            # Auto-delete stale token and fall through to full re-auth
            if "invalid_grant" in str(e) or "invalid_client" in str(e):
                log.warning("[Calendar] Token expired/revoked — clearing and re-authenticating.")
                TOKEN_FILE.unlink(missing_ok=True)
                creds = None
            else:
                raise

    # Full re-auth if no valid creds (first run or after token cleared above)
    if not creds or not creds.valid:
        flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        log.info("[Calendar] New token saved.")

    return build("calendar", "v3", credentials=creds)


# ── Time helpers ───────────────────────────────────────────

def _time_range(when: str) -> tuple:
    """
    Returns (start_iso, end_iso, label) for a time window.
    when: "today" | "tomorrow" | "week"
    """
    now = datetime.now()

    if when == "tomorrow":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        end   = start + timedelta(days=1)
        label = "tomorrow"
    elif when == "week":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=7)
        label = "the next 7 days"
    else:  # today
        start = now
        end   = now.replace(hour=23, minute=59, second=59)
        label = "today"

    return start.isoformat() + "Z", end.isoformat() + "Z", label


def _fmt_event_time(event: dict) -> str:
    """Format event start time for speech."""
    start = event["start"].get("dateTime", event["start"].get("date", ""))
    if "T" in start:
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            return dt.strftime("%I:%M %p").lstrip("0")
        except Exception:
            return start[:16]
    return "all day"


def _parse_event_command(text: str) -> tuple:
    """
    Parse natural language into (title, datetime).
    'meeting with Raj tomorrow at 3 PM' → ('Meeting with Raj', datetime)
    'dentist appointment Friday at 10'  → ('Dentist Appointment', datetime)
    """
    import dateparser

    t = text.lower().strip()

    # Strip action trigger words
    for trigger in sorted([
        "schedule a", "schedule an", "schedule",
        "add a", "add an", "add",
        "create an event called", "create an event",
        "create a", "create",
        "set up a", "set up an", "set up",
        "new event", "new meeting",
        "book a", "book an", "book",
        "put a", "put an", "put",
    ], key=len, reverse=True):
        if t.startswith(trigger):
            t = t[len(trigger):].strip()
            break

    # Patterns that signal where the time expression starts
    TIME_PATTERNS = [
        r"\btomorrow\b", r"\btoday\b",
        r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|week)\b",
        r"\bthis\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\bon\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        r"\bat\s+\d",
        r"\bin\s+\d+\s+(minute|hour|day)",
    ]

    split_pos = len(t)   # default: entire string is title
    for pattern in TIME_PATTERNS:
        m = re.search(pattern, t, re.IGNORECASE)
        if m and m.start() < split_pos:
            split_pos = m.start()

    title    = t[:split_pos].strip().strip(".,")
    time_str = t[split_pos:].strip() or "today at 10 AM"

    # Parse the time with dateparser
    dt = dateparser.parse(
        time_str,
        settings={
            "PREFER_DATES_FROM": "future",
            "TIMEZONE":           TIMEZONE,
            "RETURN_AS_TIMEZONE_AWARE": False,
        }
    )
    if not dt:
        # Fallback: tomorrow at 10 AM
        dt = datetime.now().replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        log.warning(f"[Calendar] Could not parse time '{time_str}', defaulting to tomorrow 10 AM")

    # Capitalise title
    title = " ".join(w.capitalize() for w in title.split()) if title else "New Event"
    return title, dt


# ── Triggers ───────────────────────────────────────────────

# REPLACE:
TRIGGERS = (
    "calendar", "schedule", "my schedule",
    "what do i have", "do i have anything",
    "any meetings", "any events", "upcoming events",
    # Create — every common phrasing
    "add event", "add meeting", "add appointment",
    "add to my calendar", "add to calendar", "add to the calendar",
    "add gym", "add workout", "add standup",
    "create event", "create an event", "create a event",
    "create meeting", "create a meeting", "create an appointment",
    "schedule a meeting", "schedule an event", "schedule a",
    "book a meeting", "book an appointment",
    "put on my calendar", "put in my calendar",
    "set up a meeting", "set up an event",
    # Read
    "what's on my", "what is on my",
    "next meeting", "next event",
)

_READ_TRIGGERS = (
    "what's on my calendar", "what is on my calendar",
    "my schedule", "my calendar", "what do i have",
    "do i have anything", "any meetings", "any events",
    "upcoming events", "upcoming meetings",
    "next meeting", "next event", "what's next",
)

_CREATE_TRIGGERS = (
    # add ...
    "add event", "add meeting", "add appointment",
    "add to my calendar", "add to calendar", "add to the calendar",
    # create ...
    "create event", "create an event", "create a event",
    "create meeting", "create a meeting", "create an appointment",
    # schedule / book / put / set up
    "schedule a meeting", "schedule an event", "schedule a",
    "book a meeting", "book an appointment",
    "put on my calendar", "put in my calendar",
    "set up a meeting", "set up an event",
)


# ── Action class ───────────────────────────────────────────

class CalendarAction(BaseAction):

    def can_handle(self, command: str, intent: dict) -> bool:
        c = command.lower()
        return (
            intent.get("category") == "calendar" or
            any(t in c for t in TRIGGERS)
        )

    def execute(self, command: str, context: dict) -> ActionResult:
        c       = command.lower()
        service = _get_service()

       # REPLACE with verb-first detection:
        # ── Decide: read or create? ──────────────────────────
        # Check for create FIRST using verb at start of command.
        # Prevents "add gym to my calendar" matching read trigger "my calendar".
        import re
        _is_create = (
            any(t in c for t in _CREATE_TRIGGERS) or
            bool(re.match(r"^(add|create|schedule|book|put|set)\b", c.strip()))
        )
        _is_read = not _is_create and (
            any(t in c for t in _READ_TRIGGERS) or
            "calendar" in c or
            "schedule" in c
        )

        # ── Read events ─────────────────────────────────────
        if _is_read:
            # Determine time window
            if "tomorrow" in c:
                when = "tomorrow"
            elif "week" in c or "next 7" in c:
                when = "week"
            else:
                when = "today"

            start, end, label = _time_range(when)

            result = service.events().list(
                calendarId  = "primary",
                timeMin     = start,
                timeMax     = end,
                maxResults  = 8,
                singleEvents= True,
                orderBy     = "startTime",
            ).execute()

            events = result.get("items", [])

            if not events:
                return ActionResult(
                    success = True,
                    message = f"You have nothing scheduled for {label}.",
                    data    = {"events": [], "when": label}
                )

            count  = len(events)
            prefix = f"You have {count} event{'s' if count > 1 else ''} {label}. "

            # Build spoken summary — max 4 events to keep it concise
            parts = []
            for ev in events[:4]:
                t    = _fmt_event_time(ev)
                name = ev.get("summary", "Unnamed event")
                parts.append(f"{name} at {t}" if t != "all day" else f"{name}, all day")

            summary = ". ".join(parts)
            if count > 4:
                summary += f". And {count - 4} more."

            return ActionResult(
                success = True,
                message = prefix + summary + ".",
                data    = {"events": events, "when": label}
            )

        # ── Create event ─────────────────────────────────────
        if _is_create:
            title, dt = _parse_event_command(command)

            event_body = {
                "summary": title,
                "start": {
                    "dateTime": dt.isoformat(),
                    "timeZone": TIMEZONE,
                },
                "end": {
                    "dateTime": (dt + timedelta(hours=1)).isoformat(),
                    "timeZone": TIMEZONE,
                },
            }

            created = service.events().insert(
                calendarId = "primary",
                body       = event_body,
            ).execute()

            day_label = (
                "today"    if dt.date() == datetime.now().date() else
                "tomorrow" if dt.date() == (datetime.now() + timedelta(days=1)).date() else
                dt.strftime("%A, %B %d")
            )
            time_str = dt.strftime("%I:%M %p").lstrip("0")

            return ActionResult(
                success = True,
                message = f"Done. Added {title} to your calendar for {day_label} at {time_str}.",
                data    = {"event": created}
            )

        # Fallback within handler
        return ActionResult(
            success = True,
            message = "What would you like to do with your calendar? "
                      "You can ask me to show your schedule or add a new event."
        )


# ── Module-level handler function for router compatibility ──
_calendar_action = CalendarAction()

def handle_calendar(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False
    return _calendar_action.handle(command)