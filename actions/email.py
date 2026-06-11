# actions/email.py
import base64
import re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime
from pathlib import Path
from html.parser import HTMLParser

from actions.base_action import BaseAction, ActionResult, _AuthRequired
from actions.calendar import _get_service as _get_calendar_service, CREDS_FILE, TOKEN_FILE
from config.settings import BASE_DIR
from core.logger import log

# ── Paths ──────────────────────────────────────────────────
EMAIL_CONTACTS_FILE = BASE_DIR / "config" / "email_contacts.json"

# ── Session state: last email read (for "summarize that") ──
_last_email_id:   str = ""
_last_email_body: str = ""


# ── Auth ───────────────────────────────────────────────────

def _get_gmail_service():
    """
    Reuses the Calendar OAuth token (which now includes Gmail scopes).
    Same credentials.json, same token_calendar.json.
    """
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    if not CREDS_FILE.exists():
        raise _AuthRequired(
            "Google credentials not found. "
            "Place credentials.json in your config folder."
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


# ── Email contacts ─────────────────────────────────────────

def _load_email_contacts() -> dict:
    try:
        if EMAIL_CONTACTS_FILE.exists():
            import json
            return json.loads(EMAIL_CONTACTS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.error(f"[Email] Contacts load error: {e}")
    return {}


def _find_email_address(name: str) -> str:
    """Look up email address for a contact name."""
    contacts = _load_email_contacts()
    name_lower = name.lower()
    for contact, address in contacts.items():
        if contact.lower() == name_lower or contact.lower() in name_lower:
            return address
    return ""


# ── Email parsing helpers ──────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Strip HTML tags from email body."""
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _extract_body(payload: dict, prefer_plain: bool = True) -> str:
    """Recursively extract readable text from a Gmail message payload."""
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")

    if mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
            stripper = _HTMLStripper()
            stripper.feed(html)
            return stripper.get_text()

    # Multipart — recurse
    plain_body = ""
    for part in payload.get("parts", []):
        body = _extract_body(part, prefer_plain)
        if body:
            if part.get("mimeType") == "text/plain":
                return body   # plain text is preferred
            plain_body = plain_body or body

    return plain_body


def _parse_header(headers: list, name: str) -> str:
    """Extract a specific header value from Gmail headers list."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _fmt_email_date(date_str: str) -> str:
    """Format an RFC 2822 email date for natural speech."""
    try:
        dt    = parsedate_to_datetime(date_str)
        now   = datetime.now(timezone.utc)
        delta = (now - dt.astimezone(timezone.utc))
        hours = delta.total_seconds() / 3600

        if hours < 1:
            mins = int(delta.total_seconds() / 60)
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        if hours < 24:
            h = int(hours)
            return f"{h} hour{'s' if h != 1 else ''} ago"
        if hours < 48:
            return "yesterday"
        if hours < 168:
            return dt.strftime("%A")
        return dt.strftime("%B %d")
    except Exception:
        return ""


def _clean_body(text: str, max_chars: int = 1200) -> str:
    """Clean and truncate email body for AI processing."""
    text = re.sub(r"https?://\S+", "", text)         # remove URLs
    text = re.sub(r"[\r\n]{3,}", "\n\n", text)       # collapse blank lines
    text = re.sub(r"[ \t]{2,}", " ", text)            # collapse spaces
    text = text.strip()
    return text[:max_chars]


# ── Core email operations ──────────────────────────────────

def _list_unread(service, max_results: int = 5) -> ActionResult:
    """List recent unread emails."""
    global _last_email_id, _last_email_body

    result = service.users().messages().list(
        userId     = "me",
        labelIds   = ["INBOX", "UNREAD"],
        maxResults = max_results,
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        return ActionResult(True, "Your inbox is empty. No unread emails.")

    count = len(messages)
    summaries = []

    for i, msg_ref in enumerate(messages[:5]):
        msg     = service.users().messages().get(
            userId = "me", id = msg_ref["id"], format = "metadata",
            metadataHeaders = ["From", "Subject", "Date"]
        ).execute()
        headers = msg.get("payload", {}).get("headers", [])
        sender  = _parse_header(headers, "From")
        subject = _parse_header(headers, "Subject") or "No subject"
        date    = _fmt_email_date(_parse_header(headers, "Date"))

        # Clean sender name (remove email address part)
        name_match = re.match(r"^([^<]+)", sender)
        sender_name = name_match.group(1).strip().strip('"') if name_match else sender

        when = f", {date}" if date else ""
        summaries.append(f"{sender_name} — {subject}{when}")

        # Remember first email for "read that" / "summarize that"
        if i == 0:
            _last_email_id = msg_ref["id"]

    intro = f"You have {count} unread email{'s' if count > 1 else ''}. "
    body  = ". ".join(summaries[:3])
    extra = f". And {count - 3} more." if count > 3 else "."

    return ActionResult(
        True,
        intro + body + extra,
        {"count": count, "messages": messages}
    )


def _read_email(service, identifier: str = "") -> ActionResult:
    """Read/summarize a specific email or the most recent one."""
    global _last_email_id, _last_email_body
    from core.engine import raw_query

    msg_id = _last_email_id

    # If identifier given, search for matching email
    if identifier and identifier not in ("first", "latest", "recent", "that", "it"):
        result = service.users().messages().list(
            userId = "me", maxResults = 5,
            q      = identifier,
        ).execute()
        msgs = result.get("messages", [])
        if msgs:
            msg_id = msgs[0]["id"]

    if not msg_id:
        # Default to most recent inbox message
        result = service.users().messages().list(
            userId = "me", labelIds = ["INBOX"], maxResults = 1
        ).execute()
        msgs = result.get("messages", [])
        if not msgs:
            return ActionResult(True, "No emails found in your inbox.")
        msg_id = msgs[0]["id"]

    # Fetch full message
    msg     = service.users().messages().get(
        userId = "me", id = msg_id, format = "full"
    ).execute()
    headers = msg.get("payload", {}).get("headers", [])
    subject = _parse_header(headers, "Subject") or "No subject"
    sender  = _parse_header(headers, "From")
    date    = _fmt_email_date(_parse_header(headers, "Date"))

    name_match  = re.match(r"^([^<]+)", sender)
    sender_name = name_match.group(1).strip().strip('"') if name_match else sender

    body = _clean_body(_extract_body(msg.get("payload", {})))
    _last_email_id   = msg_id
    _last_email_body = body

    if not body:
        return ActionResult(
            True,
            f"Email from {sender_name}, subject: {subject}. "
            f"The body appears to be empty or unreadable."
        )

    # Summarize with AI
    summary = raw_query(
        f"Summarize this email in 2-3 spoken sentences. "
        f"Be concise. No markdown, no bullet points.\n\n"
        f"From: {sender_name}\nSubject: {subject}\n\n{body[:1500]}",
        system=(
            "You are an email summarizer for a voice assistant. "
            "Return only a brief spoken summary. No formatting."
        )
    )

    when = f", received {date}" if date else ""
    intro = f"Email from {sender_name}{when}. Subject: {subject}. "

    # Mark as read
    try:
        service.users().messages().modify(
            userId = "me", id = msg_id,
            body   = {"removeLabelIds": ["UNREAD"]}
        ).execute()
    except Exception:
        pass

    return ActionResult(True, intro + (summary or body[:200]))


def _search_emails(service, query: str) -> ActionResult:
    """Search emails by sender name or keyword."""
    if not query:
        return ActionResult(True, "What should I search for in your emails?")

    result = service.users().messages().list(
        userId     = "me",
        q          = query,
        maxResults = 5,
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        return ActionResult(True, f"No emails found matching {query}.")

    count    = len(messages)
    subjects = []
    for msg_ref in messages[:3]:
        msg     = service.users().messages().get(
            userId = "me", id = msg_ref["id"], format = "metadata",
            metadataHeaders = ["From", "Subject", "Date"]
        ).execute()
        headers = msg.get("payload", {}).get("headers", [])
        subject = _parse_header(headers, "Subject") or "No subject"
        subjects.append(subject)

    found = f"Found {count} email{'s' if count > 1 else ''} matching {query}. "
    found += ". ".join(subjects[:3])
    if count > 3:
        found += f". And {count - 3} more."

    return ActionResult(True, found + ".")


def _send_email(service, command: str) -> ActionResult:
    """Compose and send an email from a voice command."""
    from core.engine import raw_query
    c = command.lower()

    # ── Extract recipient name ──
    contact_name = ""
    for prep in ["to ", "for "]:
        idx = c.find(prep)
        if idx != -1:
            after   = c[idx + len(prep):]
            # Take up to "saying", "that", "about", or end
            end     = len(after)
            for stop in [" saying ", " that ", " about ", " with "]:
                si = after.find(stop)
                if si != -1 and si < end:
                    end = si
            contact_name = after[:end].strip().title()
            break

    if not contact_name:
        return ActionResult(True, "Who should I send the email to?")

    email_address = _find_email_address(contact_name)
    if not email_address:
        return ActionResult(
            True,
            f"I don't have an email address for {contact_name}. "
            f"Please add it to your email contacts file."
        )

    # ── Extract message body ──
    body = command
    for strip in sorted([
        "send an email to", "send email to", "email to",
        "write an email to", "write email to",
        "compose an email to", "compose email to",
        f"to {contact_name.lower()}",
    ], key=len, reverse=True):
        body = body.lower().replace(strip, "").strip()

    for connector in ["saying that", "saying", "to say that", "to say",
                      "with the message", "that", ":"]:
        if body.lower().startswith(connector):
            body = body[len(connector):].strip()
            break

    body = body.strip().strip(".,!?")
    if not body:
        return ActionResult(True, f"What would you like to say to {contact_name}?")

    # ── Generate subject with AI ──
    subject = raw_query(
        f"Write a short email subject line (max 6 words) for: '{body}'",
        system="Return only the subject line. Nothing else."
    ) or "Message from NOVA"

    # ── Build and send ──
    msg             = MIMEText(body)
    msg["to"]       = email_address
    msg["subject"]  = subject.strip()
    raw_msg         = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    service.users().messages().send(
        userId = "me", body = {"raw": raw_msg}
    ).execute()

    log.info(f"[Email] Sent to {email_address}: {subject}")
    return ActionResult(
        True,
        f"Done. Email sent to {contact_name} with subject: {subject}."
    )


# ── Triggers ───────────────────────────────────────────────

TRIGGERS = (
    "email", "emails", "gmail", "inbox", "mail",
    "send email", "send an email", "write email", "compose email",
    "read email", "read my email", "check email", "check my email",
    "check my inbox", "my emails", "any emails", "unread emails",
    "any new emails", "new emails",
    "summarize email", "summarize that email", "summarize my email",
    "what does the email", "what did the email",
    "find emails", "search emails", "search my email",
    "emails from", "email from",
)

_READ_TRIGGERS = (
    "check email", "check my email", "check my inbox",
    "my emails", "any emails", "any new emails",
    "unread emails", "new emails", "read email",
    "read my email", "read my emails",
)

_SUMMARIZE_TRIGGERS = (
    "summarize email", "summarize that email", "summarize my email",
    "summarize the email", "what does the email say",
    "what did the email say", "read that email", "read that",
)

_SEARCH_TRIGGERS = (
    "find emails", "search emails", "search my email",
    "emails from", "email from", "find email",
)

_SEND_TRIGGERS = (
    "send email", "send an email", "write email",
    "compose email", "email to",
)


# ── Action class ───────────────────────────────────────────

class GmailAction(BaseAction):

    def can_handle(self, command: str, intent: dict) -> bool:
        c = command.lower()
        return (
            intent.get("category") == "email" or
            any(t in c for t in TRIGGERS)
        )

    def execute(self, command: str, context: dict) -> ActionResult:
        c       = command.lower()
        service = _get_gmail_service()

        # ── Send ───────────────────────────────────────────
        if any(t in c for t in _SEND_TRIGGERS):
            return _send_email(service, command)

        # ── Summarize / Read specific ──────────────────────
        if any(t in c for t in _SUMMARIZE_TRIGGERS):
            # Extract hint (e.g. "from Priya", "about project")
            hint = ""
            for kw in ["from ", "about ", "regarding "]:
                idx = c.find(kw)
                if idx != -1:
                    hint = c[idx + len(kw):].split()[0]
                    break
            return _read_email(service, hint)

        # ── Search ─────────────────────────────────────────
        if any(t in c for t in _SEARCH_TRIGGERS):
            query = c
            for t in sorted(_SEARCH_TRIGGERS, key=len, reverse=True):
                query = query.replace(t, "")
            query = query.strip().strip(".,!?")
            return _search_emails(service, query)

        # ── List unread (default) ──────────────────────────
        return _list_unread(service)


# ── Module-level handler for router ───────────────────────
_gmail_action = GmailAction()

def handle_email(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False
    return _gmail_action.handle(command)