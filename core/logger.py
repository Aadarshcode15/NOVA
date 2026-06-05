# core/logger.py
import logging
import sys
from datetime import datetime
from pathlib import Path
from config.settings import BASE_DIR

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("nova")
    logger.setLevel(logging.DEBUG)

    # ── File handler — full debug detail, one file per session ──
    session_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"session_{session_stamp}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # ── Console handler — INFO only, keeps terminal clean ──
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S"
    )
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    # ── Auto-prune: keep only the 14 most recent session logs ──
    all_logs = sorted(LOG_DIR.glob("session_*.log"))
    for old_log in all_logs[:-14]:
        try:
            old_log.unlink()
        except Exception:
            pass

    logger.info(f"Session log: {log_file.name}")
    return logger


# Single shared instance — import this everywhere
log = _setup_logger()