# actions/todo.py
import json
from core.voice import speak
from config.settings import TODO_FILE
from core.logger import log

def _load() -> list:
    try:
        if TODO_FILE.exists():
            return json.loads(TODO_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def _save(todos: list) -> None:
    try:
        TODO_FILE.write_text(json.dumps(todos, indent=2), encoding="utf-8")
    except Exception as e:
        log.error(f"[Todo] Save error: {e}")

TRIGGERS = (
    "to do", "todo", "to-do", "my list", "note", "notes",
    "add to", "remind me to", "remember to", "task"
)

def handle_todo(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    todos = _load()

    # ── Read ──
    if any(k in c for k in ("read", "show", "what's on", "list", "tell me my")):
        if not todos:
            speak("Your to-do list is empty.")
        else:
            speak(f"You have {len(todos)} item{'s' if len(todos) != 1 else ''} on your list.")
            for i, item in enumerate(todos, 1):
                speak(f"{i}. {item}")
        return True

    # ── Count ──
    if "how many" in c and ("task" in c or "todo" in c or "list" in c):
        speak(f"You have {len(todos)} item{'s' if len(todos) != 1 else ''} on your list.")
        return True

    # ── Clear ──
    if any(k in c for k in ("clear my list", "clear all", "delete all tasks", "remove all")):
        _save([])
        speak("Your to-do list has been cleared.")
        return True

    # ── Remove specific ──
    if any(k in c for k in ("delete", "remove", "done with", "complete", "finished")):
        words = c.split()
        for w in words:
            if w.isdigit():
                idx = int(w) - 1
                if 0 <= idx < len(todos):
                    removed = todos.pop(idx)
                    _save(todos)
                    speak(f"Removed: {removed}")
                else:
                    speak(f"There is no item number {w} on your list.")
                return True
        speak("Please say the number of the item you want to remove. For example, remove item 2.")
        return True

    # ── Add ──
    item = command
    for filler in sorted([
        "add to my to do list", "add to my todo list", "add to my list",
        "add to my notes", "add to list", "add a task", "add note",
        "add task", "remind me to", "remember to", "note that",
        "nova add", "sora add", "add", "note", "todo", "to do", "task"
    ], key=len, reverse=True):
        item = item.lower().replace(filler, "")
    item = item.strip().strip(".,!?")

    if not item:
        speak("What would you like to add to your list?")
        return True

    item = item[0].upper() + item[1:] if len(item) > 1 else item.upper()
    todos.append(item)
    _save(todos)
    speak(f"Added to your list: {item}. You now have {len(todos)} item{'s' if len(todos) != 1 else ''}.")
    return True