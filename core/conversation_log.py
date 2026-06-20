# core/conversation_log.py
import sqlite3
import threading
from datetime import datetime, timedelta
from config.settings import DATA_DIR
from core.logger import log

DB_PATH = DATA_DIR / "conversations.db"
_lock   = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


def init_db() -> None:
    """Call once at startup. Creates the table if it doesn't exist."""
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    assistant TEXT NOT NULL,
                    role      TEXT NOT NULL,
                    content   TEXT NOT NULL,
                    engine    TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)")
            conn.commit()
            log.info(f"[ConvLog] Database ready: {DB_PATH}")
        finally:
            conn.close()


def log_message(assistant: str, role: str, content: str, engine: str = "") -> None:
    """Insert one conversation turn. Silently no-ops on empty content."""
    if not content or not content.strip():
        return
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO messages (timestamp, assistant, role, content, engine) "
                "VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"),
                 assistant, role, content.strip(), engine)
            )
            conn.commit()
        except Exception as e:
            log.error(f"[ConvLog] Insert failed: {e}")
        finally:
            conn.close()


def search(query_text: str, limit: int = 20) -> list:
    """Substring search across all logged messages, most recent first."""
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT timestamp, assistant, role, content FROM messages "
                "WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{query_text}%", limit)
            ).fetchall()
            return rows
        finally:
            conn.close()


def get_recent(limit: int = 20) -> list:
    with _lock:
        conn = _get_conn()
        try:
            return conn.execute(
                "SELECT timestamp, assistant, role, content FROM messages "
                "ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()


def get_stats() -> dict:
    with _lock:
        conn = _get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            first = conn.execute("SELECT MIN(timestamp) FROM messages").fetchone()[0]
            return {"total": total, "since": first}
        finally:
            conn.close()


def clear_all() -> int:
    """Delete all logged conversations. Used by Settings panel."""
    with _lock:
        conn = _get_conn()
        try:
            cur = conn.execute("DELETE FROM messages")
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def prune_older_than(days: int = 90) -> int:
    """Keeps the database from growing forever. Not scheduled by default."""
    with _lock:
        conn = _get_conn()
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            cur = conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()