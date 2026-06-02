# core/lang_state.py
# Shared language state — avoids circular imports

_current_lang = "en"

LANG_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi"}

def get_lang() -> str:
    return _current_lang

def set_lang(lang: str) -> None:
    global _current_lang
    if lang in LANG_NAMES:
        _current_lang = lang
        print(f"[Voice] Language → {LANG_NAMES[lang]}")