import json
from pathlib import Path
from config.settings import BASE_DIR

CONFIG_FILE = BASE_DIR / "config" / "user_config.json"

# ── Defaults ───────────────────────────────────────────────
DEFAULTS: dict = {
    "ai": {
        "default_engine": "groq",
        "ollama_model":   "gemma4:4eb",
    },
    "voice": {
        "language":         "en",
        "whisper_model":    "small.en",
        "energy_threshold": 600,
    },
    "briefing": {
        "time":     "08:00",
        "weather":  True,
        "calendar": True,
        "todo":     True,
        "news":     False,
    },
    "general": {
        "minimize_to_tray": True,
    },
}


# ── Load / Save ────────────────────────────────────────────

def load() -> dict:
    """Load config, filling missing keys with defaults."""
    if not CONFIG_FILE.exists():
        return _deep_copy(DEFAULTS)
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return _merge(DEFAULTS, data)
    except Exception:
        return _deep_copy(DEFAULTS)


def save(config: dict) -> None:
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def get(key_path: str, default=None):
    """
    Read a nested value with dot notation.
    e.g. get("voice.language") → "en"
    """
    cfg  = load()
    keys = key_path.split(".")
    for k in keys:
        if not isinstance(cfg, dict) or k not in cfg:
            return default
        cfg = cfg[k]
    return cfg


def set_value(key_path: str, value) -> None:
    """Write a nested value with dot notation and save."""
    cfg  = load()
    keys = key_path.split(".")
    node = cfg
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = value
    save(cfg)


# ── Apply settings to running system ──────────────────────

def apply_all() -> None:
    """Call once at startup to apply saved settings."""
    cfg = load()
    _apply_engine(cfg)
    _apply_language(cfg)
    _apply_energy_threshold(cfg)
    _apply_briefing_config(cfg)


def apply_engine(engine_str: str) -> None:
    from core.engine import set_engine, Engine
    mapping = {"gemini": Engine.GEMINI, "groq": Engine.GROQ, "ollama": Engine.OLLAMA}
    e = mapping.get(engine_str.lower())
    if e:
        set_engine(e)


def apply_language(lang: str) -> None:
    from core.lang_state import set_lang
    set_lang(lang)


def apply_energy_threshold(value: int) -> None:
    """Update mic sensitivity in the running audio loop."""
    try:
        import core.voice as voice_module
        if hasattr(voice_module, "_recognizer"):
            voice_module._recognizer.energy_threshold = value
    except Exception:
        pass


def apply_briefing_time(new_time: str) -> None:
    """Reschedule the morning briefing without restarting."""
    try:
        import schedule
        from memory.proactive import morning_briefing
        schedule.clear("briefing")
        schedule.every().day.at(new_time).do(morning_briefing).tag("briefing")
    except Exception:
        pass


def apply_briefing_sections(sections: dict) -> None:
    """Toggle briefing sections (weather/calendar/todo/news) at runtime."""
    try:
        from memory.proactive import BRIEFING_CONFIG
        BRIEFING_CONFIG.update(sections)
    except Exception:
        pass


# ── Helpers ────────────────────────────────────────────────

def _deep_copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def _merge(base: dict, override: dict) -> dict:
    result = _deep_copy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


def _apply_engine(cfg: dict) -> None:
    apply_engine(cfg.get("ai", {}).get("default_engine", "groq"))


def _apply_language(cfg: dict) -> None:
    apply_language(cfg.get("voice", {}).get("language", "en"))


def _apply_energy_threshold(cfg: dict) -> None:
    apply_energy_threshold(cfg.get("voice", {}).get("energy_threshold", 600))


def _apply_briefing_config(cfg: dict) -> None:
    b = cfg.get("briefing", {})
    apply_briefing_sections({
        "weather":  b.get("weather",  True),
        "calendar": b.get("calendar", True),
        "todo":     b.get("todo",     True),
        "news":     b.get("news",     False),
    })