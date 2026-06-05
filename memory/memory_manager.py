# memory/memory_manager.py
import json
from datetime import datetime
from threading import Lock
from config.settings import MEMORY_FILE

_lock = Lock()
MAX_VALUE_LENGTH = 380
MEMORY_MAX_CHARS = 2200

# ── ADD THIS ENTIRE BLOCK above _empty_memory() ─────────────

import re as _re
import hashlib as _hashlib
import time as _time

_MEMORY_STOPWORDS = frozenset({
    'i', 'my', 'me', 'the', 'a', 'an', 'is', 'am', 'are', 'was', 'were',
    'have', 'has', 'had', 'like', 'love', 'hate', 'want', 'live', 'work',
    'that', 'this', 'it', 'in', 'on', 'at', 'to', 'for', 'of', 'and',
    'so', 'do', 'did', 'be', 'been', 'being', 'also', 'just', 'really'
})

def _make_memory_key(text: str) -> str:
    """
    Generate a collision-resistant, human-readable memory key.
    'I like coding'    → 'like_coding_3f2a'
    'I live in Mumbai' → 'live_mumbai_9c1e'
    'My name is Raj'   → 'name_raj_7b4d'
    """
    words = _re.sub(r"[^\w\s]", "", text.lower()).split()
    meaningful = [w for w in words if w not in _MEMORY_STOPWORDS and len(w) > 2]
    base = "_".join(meaningful[:3]) if meaningful else "note"
    suffix = _hashlib.md5(f"{text}{_time.time()}".encode()).hexdigest()[:4]
    return f"{base}_{suffix}"


def migrate_v1_to_v2(memory: dict) -> dict:
    """
    One-time migration: v1 had a bug where all entries in a category
    collapsed to key='i' or 'my' (stopwords). This re-keys them safely.
    Call once at startup — safe to call multiple times (idempotent).
    """
    changed = False
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        to_rekey = {k: v for k, v in items.items() if k in _MEMORY_STOPWORDS}
        for old_key, entry in to_rekey.items():
            val = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            new_key = _make_memory_key(val)
            memory[cat][new_key] = entry
            del memory[cat][old_key]
            print(f"[Memory Migration] {cat}/{old_key} → {cat}/{new_key}: {val[:40]}")
            changed = True
    if changed:
        print("[Memory Migration] Done. Keys updated.")
    return memory

# ── END OF NEW BLOCK ─────────────────────────────────────────
def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {},
    }

def load_memory() -> dict:
    if not MEMORY_FILE.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] Load error: {e}")
            return _empty_memory()

def _trim_to_limit(memory: dict) -> dict:
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
    return memory

def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    memory = _trim_to_limit(memory)
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MEMORY_FILE.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

def update_memory(category: str, key: str, value: str) -> None:
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    memory  = load_memory()
    new_val = value.strip()[:MAX_VALUE_LENGTH]
    entry   = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
    if memory[category].get(key, {}).get("value") != new_val:
        memory[category][key] = entry
        save_memory(memory)
        print(f"[Memory] Saved → {category}/{key}: {new_val}")

def forget_memory(category: str, key: str) -> bool:
    memory = load_memory()
    if key in memory.get(category, {}):
        del memory[category][key]
        save_memory(memory)
        return True
    return False

def clear_memory() -> None:
    save_memory(_empty_memory())

def format_memory_for_prompt(memory: dict) -> str:
    if not memory:
        return ""
    lines = []
    identity  = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_',' ').title()}: {val}")

    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("\nPreferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_',' ').title()}: {val}")

    projects = memory.get("projects", {})
    if projects:
        lines.append("\nActive Projects:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_',' ').title()}: {val}")

    rels = memory.get("relationships", {})
    if rels:
        lines.append("\nPeople:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_',' ').title()}: {val}")

    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("\nWishes / Plans:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_',' ').title()}: {val}")

    notes = memory.get("notes", {})
    if notes:
        lines.append("\nNotes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""
    result = "[WHAT YOU KNOW ABOUT THIS PERSON]\n" + "\n".join(lines)
    return result[:2000] + "\n"

def get_memory_summary() -> str:
    memory = load_memory()
    parts  = []
    for cat, items in memory.items():
        if not isinstance(items, dict) or not items:
            continue
        entries = []
        for key, entry in items.items():
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                entries.append(f"{key.replace('_',' ')}: {val}")
        if entries:
            parts.append(f"{cat.title()} — " + ", ".join(entries))
    if not parts:
        return "I don't have anything saved in memory yet."
    return "Here is what I remember. " + ". ".join(parts) + "."
