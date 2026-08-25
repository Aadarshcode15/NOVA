# core/perf.py
import time
import threading
from collections import deque
from core.logger import log

_lock = threading.Lock()

# Current in-flight turn's stage timestamps (ms since turn start)
_turn: dict = {}

# Rolling history of completed turns, for session-level averages
_history: deque = deque(maxlen=50)

# Stages tracked, in chronological order
STAGES = ["stt", "intent", "queued", "first_audio"]


def start_turn() -> None:
    """Call the instant audio capture finishes (user stopped speaking)."""
    with _lock:
        _turn.clear()
        _turn["_start"] = time.perf_counter()


def mark(stage: str) -> None:
    """Record elapsed ms since turn start for a stage. Overwrites on repeat calls."""
    with _lock:
        if "_start" not in _turn:
            return
        _turn[stage] = (time.perf_counter() - _turn["_start"]) * 1000


def mark_once(stage: str) -> bool:
    """
    Like mark(), but only records on the FIRST call per turn for this stage.
    Returns True if this call performed the mark.
    Used for stages that may fire multiple times in one turn (e.g. a handler
    queuing several TTS sentences) where only the first occurrence matters.
    """
    with _lock:
        if "_start" not in _turn or stage in _turn:
            return False
        _turn[stage] = (time.perf_counter() - _turn["_start"]) * 1000
        return True


def end_turn(command_preview: str = "") -> dict:
    """
    Finalises the current turn: computes per-stage deltas, logs a summary,
    stores it in rolling history, resets for the next turn.
    """
    with _lock:
        if "_start" not in _turn:
            return {}
        total_ms = (time.perf_counter() - _turn["_start"]) * 1000

        ordered   = [s for s in STAGES if s in _turn]
        breakdown = {}
        prev      = 0.0
        for stage in ordered:
            breakdown[stage] = round(_turn[stage] - prev, 0)
            prev = _turn[stage]
        breakdown["total"] = round(total_ms, 0)

        _history.append(breakdown)
        _turn.clear()

    parts  = " | ".join(f"{k}:{v:.0f}ms" for k, v in breakdown.items() if k != "total")
    suffix = f" — '{command_preview[:40]}'" if command_preview else ""
    log.info(f"[Perf] {parts} | TOTAL:{breakdown['total']:.0f}ms{suffix}")
    return breakdown


def get_session_stats() -> dict:
    """Avg/min/max/count per stage across the rolling session history."""
    with _lock:
        if not _history:
            return {}
        stats = {}
        for stage in STAGES + ["total"]:
            values = [h[stage] for h in _history if stage in h]
            if values:
                stats[stage] = {
                    "avg":   round(sum(values) / len(values), 0),
                    "min":   round(min(values), 0),
                    "max":   round(max(values), 0),
                    "count": len(values),
                }
        return stats


def log_session_stats() -> None:
    """Called at shutdown — prints a clean summary table."""
    stats = get_session_stats()
    if not stats:
        return
    log.info("[Perf] ── Session Performance Summary ──")
    for stage, s in stats.items():
        log.info(
            f"[Perf]   {stage:12s} avg:{s['avg']:.0f}ms  "
            f"min:{s['min']:.0f}ms  max:{s['max']:.0f}ms  (n={s['count']})"
        )