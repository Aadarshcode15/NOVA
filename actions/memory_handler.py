# actions/memory_handler.py
from PIL.Image import item

from core.voice import speak
from core.logger import log
from memory.memory_manager import (
    update_memory, forget_memory, clear_memory,
    get_memory_summary, load_memory, save_memory
)

MEMORY_CATEGORIES = {
    "name":       "identity",
    "age":        "identity",
    "city":       "identity",
    "job":        "identity",
    "birthday":   "identity",
    "language":   "identity",
    "favorite":   "preferences",
    "prefer":     "preferences",
    "like":       "preferences",
    "hate":       "preferences",
    "dislike":    "preferences",
    "project":    "projects",
    "building":   "projects",
    "working on": "projects",
    "friend":     "relationships",
    "family":     "relationships",
    "sister":     "relationships",
    "brother":    "relationships",
    "mom":        "relationships",
    "dad":        "relationships",
    "want to":    "wishes",
    "plan to":    "wishes",
    "wish":       "wishes",
    "dream":      "wishes",
}

def _detect_category(text: str) -> str:
    for keyword, cat in MEMORY_CATEGORIES.items():
        if keyword in text:
            return cat
    return "notes"

TRIGGERS = (
    "remember", "forget", "what do you know",
    "what do you remember", "clear memory", "your memory",
    "erase memory"
)

def handle_memory(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    # ── Read ──
    if any(k in c for k in ("what do you know", "what do you remember", "your memory")):
        speak(get_memory_summary())
        return True

    # ── Clear all ──
    if any(k in c for k in ("clear memory", "forget everything", "erase memory", "wipe memory")):
        clear_memory()
        speak("Memory cleared. I have forgotten everything.")
        return True

    # ── Forget specific ──
    if "forget" in c:
        item = c.replace("forget", "").strip().strip(".,!?")
        if not item:
            speak("What should I forget?")
            return True
        cat = _detect_category(item)
        key = item.replace(" ", "_").lower()
        if forget_memory(cat, key):
            speak(f"Done. I have forgotten {item}.")
        else:
            speak(f"I don't have anything saved about {item}.")
        return True

    # ── Save ──
    if "remember" in c:
        item = command
        for filler in sorted([
            "please remember that", "please remember",
            "remember that", "remember",
            "nova remember", "sora remember"
        ], key=len, reverse=True):
            item = item.lower().replace(filler, "")
        item = item.strip().strip(".,!?")

        if not item:
            speak("What would you like me to remember?")
            return True

        # REPLACE WITH:
        from memory.memory_manager import _make_memory_key
        cat = _detect_category(item)
        key = _make_memory_key(item)
        update_memory(cat, key, item)
        speak("Got it. I will remember that.")
        return True

    return False