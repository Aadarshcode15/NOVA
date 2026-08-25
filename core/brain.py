# core/brain.py
"""
NOVA Behavioral Intelligence Layer.

Mines conversation history to build a dynamic behavioral context
that is injected into every AI prompt. This is the closest thing
to "teaching" an AI without fine-tuning — structured, evidence-based
context that makes responses significantly more relevant and personal.

Updated once per session at startup (not every query — too slow).
Cached in memory for the session duration.
"""

import json
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from config.settings import DATA_DIR
from core.logger import log

DB_PATH    = DATA_DIR / "conversations.db"
_lock      = threading.Lock()
_cache: str = ""          # session-level cache of the built context
_built     = False


# ── Mining functions ──────────────────────────────────────

def _get_conn():
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def _top_topics(days: int = 30, limit: int = 8) -> list:
    """Most frequently asked-about topics in the last N days."""
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn   = _get_conn()
        rows   = conn.execute(
            "SELECT content FROM messages WHERE role='user' AND timestamp > ? ORDER BY timestamp DESC LIMIT 200",
            (cutoff,)
        ).fetchall()
        conn.close()

        # Simple keyword extraction — count meaningful words
        STOPWORDS = frozenset({
            'what', 'who', 'how', 'is', 'the', 'a', 'an', 'in', 'on', 'at', 'to',
            'for', 'of', 'and', 'or', 'me', 'my', 'i', 'do', 'does', 'can', 'you',
            'tell', 'please', 'nova', 'sora', 'okay', 'yes', 'no', 'it', 'that',
            'this', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
        })
        words = []
        for (content,) in rows:
            for w in content.lower().split():
                clean = w.strip(".,!?\"'")
                if len(clean) > 3 and clean not in STOPWORDS:
                    words.append(clean)

        counts = Counter(words).most_common(limit)
        return [word for word, _ in counts if len(word) > 3]
    except Exception as e:
        log.debug(f"[Brain] Topic mining failed: {e}")
        return []


def _usage_by_hour() -> dict:
    """Which hours of day user is most active."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT timestamp FROM messages WHERE role='user' ORDER BY timestamp DESC LIMIT 500"
        ).fetchall()
        conn.close()
        hours = [int(r[0][11:13]) for r in rows if len(r[0]) > 13]
        if not hours:
            return {}
        counts = Counter(hours)
        peak   = counts.most_common(3)
        return {h: c for h, c in peak}
    except Exception:
        return {}


def _command_categories(days: int = 14) -> list:
    """Most used command categories recently."""
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn   = _get_conn()
        rows   = conn.execute(
            "SELECT content FROM messages WHERE role='user' AND timestamp > ? LIMIT 300",
            (cutoff,)
        ).fetchall()
        conn.close()

        CATEGORY_HINTS = {
            "music":    ["play", "song", "music", "spotify", "pause", "next"],
            "search":   ["who is", "what is", "tell me", "search", "find"],
            "weather":  ["weather", "temperature", "rain"],
            "code":     ["code", "write", "create", "build", "html", "python"],
            "calendar": ["calendar", "schedule", "meeting", "event"],
            "email":    ["email", "gmail", "inbox", "mail"],
            "news":     ["news", "headline"],
            "reminder": ["remind", "reminder", "alarm"],
        }

        cat_counts: Counter = Counter()
        for (content,) in rows:
            cl = content.lower()
            for cat, hints in CATEGORY_HINTS.items():
                if any(h in cl for h in hints):
                    cat_counts[cat] += 1

        return [cat for cat, _ in cat_counts.most_common(5)]
    except Exception:
        return []


def _total_conversations() -> int:
    try:
        conn  = _get_conn()
        count = conn.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _recent_context(limit: int = 6) -> list:
    """Last few exchanges for immediate context relevance."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT role, content FROM messages ORDER BY timestamp DESC LIMIT ?",
            (limit * 2,)
        ).fetchall()
        conn.close()
        return list(reversed(rows))
    except Exception:
        return []


# ── Context builder ───────────────────────────────────────

def build_behavioral_context() -> str:
    """
    Builds a structured behavioral context string from conversation history.
    Called once per session at startup. Returns empty string if no history.
    """
    global _cache, _built

    with _lock:
        if _built:
            return _cache

        total = _total_conversations()
        if total < 5:
            # Not enough history to derive meaningful patterns
            _built = True
            _cache = ""
            return ""

        lines = ["[BEHAVIORAL CONTEXT — learned from usage history]"]

        # Usage volume
        lines.append(f"Total interactions logged: {total}")

        # Top topics
        topics = _top_topics(days=30)
        if topics:
            lines.append(f"Frequent topics (last 30 days): {', '.join(topics[:6])}")

        # Most used command categories
        cats = _command_categories(days=14)
        if cats:
            lines.append(f"Most used features (last 14 days): {', '.join(cats)}")

        # Active hours
        peak_hours = _usage_by_hour()
        if peak_hours:
            hour_strs = []
            for h in sorted(peak_hours.keys()):
                period = "AM" if h < 12 else "PM"
                display = h if h <= 12 else h - 12
                hour_strs.append(f"{display}{period}")
            lines.append(f"Typically active at: {', '.join(hour_strs)}")

        _cache = "\n".join(lines)
        _built = True
        log.info(f"[Brain] Behavioral context built ({total} interactions, {len(cats)} categories)")
        return _cache


# ── Few-shot examples ─────────────────────────────────────
# These teach the AI exactly how to handle NOVA-specific commands.
# Unlike general chat, NOVA responses must be ≤2 sentences, spoken-friendly,
# no markdown. These examples reinforce that format.

NOVA_FEW_SHOT = """
[NOVA RESPONSE EXAMPLES — follow this format exactly]

User: play something chill
NOVA: Playing a chill playlist on Spotify for you.

User: who is Sachin Tendulkar
NOVA: Sachin Tendulkar is a legendary Indian cricketer widely regarded as one of the greatest batsmen of all time, with 100 international centuries to his name.

User: what is machine learning
NOVA: Machine learning is a branch of AI where systems learn patterns from data to make predictions or decisions without being explicitly programmed for each task.

User: open youtube and play lo-fi music
NOVA: Opening YouTube and searching for lo-fi music now.

User: remind me to call mom at 6 PM
NOVA: Done, I will remind you to call mom at 6 PM today.

User: write code for a login form in HTML
NOVA: Writing a complete HTML login form with styling. One moment.

User: what is on my calendar today
NOVA: You have two events today: standup at 10 AM and gym at 6 PM.

User: summarize my emails
NOVA: You have 3 unread emails. One from Raj about the project update, one newsletter, and one from Google about your account.
[END EXAMPLES]
"""


def get_few_shot_examples() -> str:
    """Returns the few-shot example block for injection into prompts."""
    return NOVA_FEW_SHOT


# ── Public API ────────────────────────────────────────────

def get_full_brain_context() -> str:
    """
    Returns the complete brain context block for prompt injection.
    Combines behavioral patterns + few-shot examples.
    """
    behavioral = build_behavioral_context()
    few_shot   = get_few_shot_examples()
    parts = []
    if behavioral:
        parts.append(behavioral)
    parts.append(few_shot)
    return "\n\n".join(parts)


def reset_cache() -> None:
    """Call if you want to force a rebuild (e.g. after clearing history)."""
    global _built, _cache
    with _lock:
        _built = False
        _cache = ""