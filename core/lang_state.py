# core/lang_state.py
# Shared language state — avoids circular imports
from core.logger import log
_current_lang = "en"

LANG_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi"}

def get_lang() -> str:
    return _current_lang

def set_lang(lang: str) -> None:
    global _current_lang
    if lang in LANG_NAMES:
        _current_lang = lang
        print(f"[Voice] Language → {LANG_NAMES[lang]}")

# In detect_lang_switch(), the triggers already have "back to english"
# But add a timeout — if no Hindi/Marathi command in 5 minutes, auto-reset:

# Add to lang_state.py:
import time
_lang_set_time: float = 0.0

def set_lang(lang: str) -> None:
    global _current_lang, _lang_set_time
    if lang in LANG_NAMES:
        _current_lang = lang
        _lang_set_time = time.time()
        print(f"[Voice] Language → {LANG_NAMES[lang]}")

def get_lang() -> str:
    global _current_lang, _lang_set_time
    # Auto-reset to English after 5 minutes of inactivity in Indic mode
    if _current_lang != "en" and _lang_set_time > 0:
        if time.time() - _lang_set_time > 300:
            _current_lang = "en"
            log.info("[Voice] Language auto-reset to English (5min timeout).")
    return _current_lang