# core/intent.py
import json
import re
import threading
from pathlib import Path
from config.settings import BASE_DIR, GROQ_API_KEY, GROQ_MODEL
from core.logger import log

# ── Persistent cache ───────────────────────────────────────
# Survives restarts — "play something chill" only hits Groq once ever.
_CACHE_FILE = BASE_DIR / "data" / "intent_cache.json"
_cache: dict = {}
_cache_lock  = threading.Lock()

def _load_cache() -> None:
    global _cache
    try:
        if _CACHE_FILE.exists():
            _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            log.info(f"[Intent] Loaded {len(_cache)} cached patterns.")
    except Exception:
        _cache = {}

def _save_to_cache(key: str, value: dict) -> None:
    with _cache_lock:
        _cache[key] = value
        try:
            _CACHE_FILE.write_text(
                json.dumps(_cache, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"[Intent] Cache write failed: {e}")

_load_cache()


# ── Context tracking ───────────────────────────────────────
# Remembers the last category so "what about in Tokyo?"
# is understood as a follow-up weather query.
_last_category = "general"


# ── Fast path — regex patterns (no API call) ───────────────
# Covers ~60% of daily commands instantly.
_FAST_INTENTS: list[tuple] = [
    # System
    (r"^(what'?s?|what is) the time\??$",                   "system",  "time",       {}),
    (r"^(what'?s?|what is) (today'?s? )?date\??$",          "system",  "date",       {}),
    (r"^(check |my )?battery\??$",                           "system",  "battery",    {}),
    (r"^(take a? )?screenshot$",                             "system",  "screenshot", {}),
    (r"^(mute|unmute)$",                                     "system",  "volume",     {}),
    (r"^volume (up|down)$",                                  "system",  "volume",     {}),
    (r"^set volume to (\d+)$",                               "system",  "volume",     {}),
    (r"^brightness (up|down)$",                              "system",  "brightness", {}),
    (r"^open .+",                                            "system",  "open",       {}),
    (r"^launch .+",                                          "system",  "open",       {}),

    # Spotify
    (r"^(pause|stop) (music|spotify|song|the music)$",       "spotify", "pause",      {}),
    (r"^(resume|continue|unpause)( music| spotify)?$",       "spotify", "resume",     {}),
    (r"^(next|skip)( song| track| one)?$",                   "spotify", "next",       {}),
    (r"^(previous|last|go back)( song| track)?$",            "spotify", "previous",   {}),
    (r"^what'?s? (playing|on|the song)$",                    "spotify", "current",    {}),

    # Weather
    (r"^(what'?s?|how'?s?) the weather",                     "weather", "current",    {}),
    (r"^weather( today| now| forecast)?$",                   "weather", "current",    {}),
    (r"^is it (raining|sunny|cold|hot)",                     "weather", "current",    {}),

    # News
    (r"^(today'?s?|latest|top|any)? ?(news|headlines)$",    "news",    "general",    {}),
    (r"^(tech|sports?|business|health|science) news$",       "news",    "category",   {}),

    # Todo
    (r"^(show|read|list|what'?s? on) my (to.?do|list|tasks)","todo",    "read",       {}),
    (r"^(add .+ to my list|add .+ to my to.?do)",            "todo",    "add",        {}),
    (r"^how many (tasks|items|things on)",                   "todo",    "count",      {}),

    # Memory
    (r"^(what do you know|what do you remember)",            "memory",  "read",       {}),
    (r"^remember (that )?",                                  "memory",  "save",       {}),
    (r"^(clear|wipe|erase|forget) (my )?memory$",           "memory",  "clear",      {}),

    # Vision
    (r"^(what'?s? on (my )?screen|look at my screen)",       "vision",  "describe",   {}),
    (r"^(describe|analyse|analyze) (my )?screen$",           "vision",  "describe",   {}),

    # Calendar
    (r"^(what'?s?|do i have|check) (on |my )?calendar",  "calendar", "read",   {}),
    (r"^(my|today'?s?|tomorrow'?s?) schedule$",           "calendar", "read",   {}),
    (r"^(what do i have|do i have anything) (today|tomorrow|this week)", "calendar", "read", {}),
    (r"^(any|my) (meetings?|events?|appointments?) (today|tomorrow)",    "calendar", "read", {}),
    (r"^(add|create|schedule|book) (a |an )?(meeting|event|appointment)","calendar", "create",{}),
    (r"^(what'?s? my next|next) (meeting|event)$",        "calendar", "read",   {}),

    # Email
    (r"^(check|read|get) my (emails?|inbox|gmail|mail)$",     "email", "read",   {}),
    (r"^(any|do i have|check for) (new |unread )?(emails?|mail)","email","read",  {}),
    (r"^(send|write|compose) (an? )?email",                    "email", "send",   {}),
    (r"^(summarize|read) (that |my |the )?(last |latest )?email","email","read",  {}),
    (r"^email(s?) from\b",                                     "email", "search", {}),

    # Browser
    (r"^browse to\b",                                      "browser", "navigate", {}),
    (r"^(search|find) (jobs )?on (amazon|flipkart|linkedin|github)", "browser", "search", {}),
    (r"^close (the )?browser$",                             "browser", "close",    {}),
]

def _fast_classify(text: str) -> dict | None:
    """Returns intent dict if a regex matches, else None."""
    for pattern, category, action, entities in _FAST_INTENTS:
        if re.search(pattern, text, re.IGNORECASE):
            return {
                "category":         category,
                "confidence":       0.99,
                "action":           action,
                "target":           "",
                "entities":         entities,
                "context_dependent": False,
            }
    return None


# ── Context-dependency detector ────────────────────────────
_CONTEXT_SIGNALS = (
    r"^(what|how) about\b",
    r"^and (in|for|at|what)\b",
    r"^(more|less|another|different|something else)\b",
    r"^\b(it|that|this|those|them)\b",
    r"^instead\b",
    r"^rather\b",
)

def _is_context_dependent(text: str) -> bool:
    for pattern in _CONTEXT_SIGNALS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ── AI classification prompt ────────────────────────────────
_PROMPT = """\
Classify this voice assistant command. Return ONLY a single JSON object — no markdown, no explanation.

Categories (pick exactly one):
  spotify   - music playback, songs, playlists, artists
  weather   - weather conditions, temperature, forecast
  news      - headlines, current events, news topics
  reminder  - set reminders, alarms, countdowns
  todo      - to-do list, tasks, notes
  whatsapp  - send messages, text contacts
  system    - open apps, volume, brightness, screenshot, battery, clipboard
  youtube   - play videos, search YouTube, summarise videos
  files     - create/find/read files and folders
  code      - write, run, explain, fix code
  search    - factual questions, web lookups, general knowledge
  memory    - remember/forget personal info about the user
  vision    - describe or analyse the screen
  desktop   - wallpaper, organise desktop
  browser   - search/browse specific websites (Amazon, Flipkart, LinkedIn, GitHub), click page elements
  general   - anything that doesn't fit above

JSON schema (all fields required):
{{
  "category": "one of the above",
  "confidence": 0.0-1.0,
  "action": "main verb (play/open/send/set/search/remind/...)",
  "target": "main noun/object",
  "entities": {{
    "time":    "time expression or empty string",
    "contact": "person name or empty string",
    "mood":    "style/emotional qualifier or empty string",
    "value":   "number/setting or empty string"
  }},
  "context_dependent": true or false
}}

context_dependent = true when command refers to something from a previous turn:
  pronouns (it/that/this), "what about", "more/less/another", "instead"

Examples:
  "play something chill"
  → {{"category":"spotify","confidence":0.95,"action":"play","target":"music","entities":{{"mood":"chill"}},"context_dependent":false}}

  "what about in Mumbai"
  → {{"category":"weather","confidence":0.88,"action":"check","target":"weather","entities":{{}},"context_dependent":true}}

  "remind me to call mom at 6 PM"
  → {{"category":"reminder","confidence":0.99,"action":"remind","target":"call mom","entities":{{"time":"6 PM"}},"context_dependent":false}}

  "something more upbeat"
  → {{"category":"spotify","confidence":0.90,"action":"play","target":"music","entities":{{"mood":"upbeat"}},"context_dependent":true}}

Previous category: {prev}
Command: {cmd}"""


def _call_groq(command: str, prev_category: str) -> dict:
    """Direct low-temperature Groq call — bypasses history tracking."""
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp   = client.chat.completions.create(
        model       = GROQ_MODEL,
        messages    = [{"role": "user", "content": _PROMPT.format(cmd=command, prev=prev_category)}],
        temperature = 0.1,    # deterministic JSON
        max_tokens  = 160,
    )
    raw = resp.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


# ── Public API ─────────────────────────────────────────────
def classify(command: str) -> dict:
    """
    Classify a voice command into a structured intent dict.

    Flow:
      1. Fast path  — regex match (instant, no API)
      2. Cache hit  — already classified before (instant, no API)
      3. Groq call  — AI classification (cached after first call)
      4. Fallback   — keyword heuristic if Groq fails
    """
    global _last_category

    text     = command.strip()
    cache_key = text.lower()

    # ── 1. Fast path ──
    fast = _fast_classify(text)
    if fast:
        _last_category = fast["category"]
        log.debug(f"[Intent] Fast: {fast['category']} ({fast['confidence']:.0%})")
        return fast

    # ── 2. Cache hit ──
    with _cache_lock:
        if cache_key in _cache:
            cached = _cache[cache_key]
            _last_category = cached["category"]
            log.debug(f"[Intent] Cache: {cached['category']} ({cached['confidence']:.0%})")
            return cached

    # ── 3. Groq AI classification ──
    try:
        result = _call_groq(text, _last_category)
        # If context_dependent and last category is known, inherit it if confidence is low
        if result.get("context_dependent") and result.get("confidence", 0) < 0.75:
            result["category"]   = _last_category
            result["confidence"] = 0.80
            log.debug(f"[Intent] Context inherited: {_last_category}")

        _last_category = result["category"]
        _save_to_cache(cache_key, result)
        log.info(f"[Intent] Groq: {result['category']} ({result.get('confidence', 0):.0%}) ← {text[:50]}")
        return result

    except Exception as e:
        log.warning(f"[Intent] Groq classification failed: {e}")

    # ── 4. Keyword fallback ──
    fallback = _keyword_fallback(cache_key)
    _last_category = fallback["category"]
    return fallback


def _keyword_fallback(text: str) -> dict:
    """Last-resort keyword heuristic if Groq is unavailable."""
    rules = [
        (("play", "song", "music", "spotify", "playlist"),          "spotify"),
        (("weather", "temperature", "forecast", "raining"),         "weather"),
        (("news", "headline", "today"),                             "news"),
        (("remind", "reminder", "alarm"),                           "reminder"),
        (("todo", "to do", "task", "list"),                         "todo"),
        (("calendar", "schedule", "meeting", "appointment", "event"),   "calendar"),
        (("browse", "amazon", "flipkart", "linkedin job"),               "browser"),
        (("email", "gmail", "inbox", "mail", "unread"),                 "email"),
        (("whatsapp", "message", "send", "text"),                   "whatsapp"),
        (("open", "launch", "volume", "brightness", "battery"),     "system"),
        (("youtube", "video", "watch"),                             "youtube"),
        (("file", "folder", "document"),                            "files"),
        (("code", "script", "program"),                             "code"),
        (("what is", "who is", "how to", "search", "find"),         "search"),
        (("remember", "forget", "memory"),                          "memory"),
        (("screen", "look at"),                                     "vision"),
    ]
    for keywords, category in rules:
        if any(k in text for k in keywords):
            return {"category": category, "confidence": 0.60,
                    "action": "", "target": "", "entities": {},
                    "context_dependent": False}
    return {"category": "general", "confidence": 0.50,
            "action": "", "target": "", "entities": {},
            "context_dependent": False}


def get_last_category() -> str:
    return _last_category