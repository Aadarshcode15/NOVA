# actions/code_helper.py
import os
import re
import sys
import subprocess
import winreg
from datetime import datetime
from pathlib import Path
from core.voice import speak
from core.engine import query
from core.logger import log


# ── Workspace ──────────────────────────────────────────────

def _get_desktop() -> Path:
    """
    Returns the actual Desktop path on Windows.
    Handles OneDrive redirection (C:/Users/X/OneDrive/Desktop)
    which breaks Path.home() / 'Desktop'.
    """
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        ) as key:
            desktop = winreg.QueryValueEx(key, "Desktop")[0]
            p = Path(desktop)
            if p.exists():
                return p
    except Exception:
        pass
    return Path.home() / "Desktop"


# Create workspace folder on import
try:
    CODE_DIR = _get_desktop() / "Nova Code Helper"
    CODE_DIR.mkdir(parents=True, exist_ok=True)
    log.info(f"[Code] Workspace ready: {CODE_DIR}")
except Exception as e:
    CODE_DIR = Path.home() / "Nova Code Helper"
    CODE_DIR.mkdir(parents=True, exist_ok=True)
    log.warning(f"[Code] Fallback workspace: {CODE_DIR} ({e})")


# ── Language detection ─────────────────────────────────────

_LANG_MAP = {
    "python":      (".py",   "python",     sys.executable),
    "javascript":  (".js",   "javascript", "node"),
    "js":          (".js",   "javascript", "node"),
    "html":        (".html", "html",       None),
    "css":         (".css",  "css",        None),
    "java":        (".java", "java",       "java"),
    "c++":         (".cpp",  "c++",        None),
    "cpp":         (".cpp",  "c++",        None),
    "sql":         (".sql",  "sql",        None),
    "bash":        (".sh",   "bash",       "bash"),
    "shell":       (".sh",   "bash",       "bash"),
    "typescript":  (".ts",   "typescript", "ts-node"),
    "kotlin":      (".kt",   "kotlin",     None),
    "go":          (".go",   "go",         "go run"),
    "ruby":        (".rb",   "ruby",       "ruby"),
}
# ── Natural language code request detector ─────────────────
# Catches "create an HTML page", "build a calculator", "write a login form"
# without requiring the word "code" to be present.

_CREATE_VERBS = frozenset({
    "write", "create", "generate", "build", "make",
    "code", "develop", "implement", "design",
})

_CODE_SIGNALS = frozenset({
    # Languages
    "html", "css", "javascript", "python", "java", "sql",
    "bash", "typescript", "kotlin", "rust", "golang",
    # Artefact types (things you code)
    "page", "website", "webpage", "web page", "form", "script",
    "program", "app", "application", "function", "algorithm",
    "calculator", "game", "api", "class", "module", "component",
    "database", "query", "bot", "chatbot", "tool", "utility",
    "dashboard", "login", "signup", "todo", "to-do", "portfolio",
    "animation", "chart", "graph", "scraper", "converter",
})

def _is_code_request(text: str) -> bool:
    """
    Returns True for natural language code creation requests
    that don't contain the word 'code' explicitly.
    Examples:
      "create an HTML page with a contact form"  → True
      "build a calculator in Python"             → True
      "write a login form"                       → True
      "open file explorer"                       → False
    """
    t = text.lower()
    has_verb   = any(t.startswith(v + " ") or f" {v} " in t for v in _CREATE_VERBS)
    has_signal = any(s in t for s in _CODE_SIGNALS)
    return has_verb and has_signal

# Checked in this priority order.
# HTML before JS/CSS so "website using HTML, CSS, JS" → HTML as primary file.
_LANG_PRIORITY = [
    "python", "html", "javascript", "typescript",
    "java", "css", "kotlin", "rust", "ruby",
    "bash", "shell", "sql", "cpp", "c++",
]

# Too short/ambiguous for word-boundary matching alone
_STRICT_KEYWORDS = {"js", "go", "c", "r"}


def _detect_language(text: str) -> tuple:
    """
    Detect programming language from task description.
    Uses word-boundary regex so 'html page', 'python script',
    'javascript function' all match correctly.
    Defaults to Python if nothing found.
    """
    import re
    t = text.lower()

    for keyword in _LANG_PRIORITY:
        if keyword not in _LANG_MAP:
            continue
        ext, lang, runner = _LANG_MAP[keyword]

        if keyword in _STRICT_KEYWORDS:
            # Short keywords need explicit context to avoid false matches
            if any(p in t for p in [f"in {keyword} ", f"using {keyword}", f"{keyword} code"]):
                return ext, lang, runner
        else:
            # Full language names: match as whole word anywhere in text
            if re.search(r'\b' + re.escape(keyword) + r'\b', t):
                return ext, lang, runner

    return ".py", "python", sys.executable


def _sanitize_name(text: str) -> str:
    """Convert task description to a clean filename slug."""
    STRIP_WORDS = [
        # Action verbs
        "write", "create", "generate", "make", "build", "code",
        "develop", "implement", "design",
        # Artefact nouns (redundant with extension)
        "program", "script", "function", "code",
        # Connectors
        "using", "with", "and", "or", "for", "that", "which",
        "the", " an ", " a ",
        # Language names (already in extension)
        "python", "javascript", "typescript", "java", "html", "css",
        "sql", "bash", "kotlin", "rust", "ruby", "golang",
    ]
    name = text.lower()
    for word in sorted(STRIP_WORDS, key=len, reverse=True):
        name = name.replace(word, " ")
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip()).strip("_")
    # Remove trailing connectors left after stripping
    name = re.sub(r"_(and|or|the|a|an|in|of|to)$", "", name)
    return name[:35] or "code"


# ── File helpers ───────────────────────────────────────────

_CODE_EXTENSIONS = {".py", ".js", ".html", ".css", ".java",
                    ".cpp", ".sql", ".sh", ".ts", ".kt", ".go", ".rb"}

def _all_files() -> list:
    """All code files in CODE_DIR, newest first."""
    files = [
        f for f in CODE_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in _CODE_EXTENSIONS
        and not f.stem.endswith("_backup")
    ]
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def _find_file(hint: str = "") -> Path | None:
    """Find a code file in CODE_DIR from a partial name hint."""
    files = _all_files()
    if not files:
        return None
    if not hint.strip():
        return files[0]   # most recent
    h = hint.lower().replace(" ", "_")
    # Exact stem match
    for f in files:
        if f.stem.lower() == h:
            return f
    # Partial match
    for f in files:
        if h in f.stem.lower():
            return f
    # Word overlap match
    hint_words = set(h.replace("_", " ").split())
    for f in files:
        stem_words = set(f.stem.lower().replace("_", " ").split())
        if len(hint_words & stem_words) >= 2:
            return f
    return None


def _open_in_editor(fpath: Path) -> None:
    """Open file in VS Code if available, else default app."""
    try:
        subprocess.Popen(f'code "{fpath}"', shell=True)
        return
    except Exception:
        pass
    try:
        os.startfile(str(fpath))
    except Exception as e:
        log.warning(f"[Code] Couldn't open editor: {e}")


def _speak_files_available(files: list) -> None:
    """Tell user what files are available to act on."""
    if not files:
        speak("The Nova Code Helper folder is empty. Ask me to write some code first.")
        return
    names = [f.stem.replace("_", " ") for f in files[:3]]
    speak(
        f"Which file? Available: {', '.join(names)}"
        + (f" and {len(files)-3} more." if len(files) > 3 else ".")
    )


# ── Trigger groups ─────────────────────────────────────────

TRIGGERS = (
    "write code", "write a code", "create code", "generate code",
    "code for", "code to", "write a program", "write program",
    "run code", "run the code", "execute code", "run script",
    "explain code", "explain the code", "what does this code",
    "fix code", "fix the code", "debug code", "debug the code",
    "write a script", "write script", "code a",
    "list my codes", "list codes", "what codes", "show my codes",
    "open code", "open the code",
)

_WRITE  = ("write code", "write a code", "generate code", "create code",
           "code for", "code to", "write a program", "write program",
           "write a script", "write script", "code a",)

_RUN    = ("run code", "run the code", "execute code", "run script",
           "execute script", "execute the code",)

_EXPLAIN= ("explain code", "explain the code", "what does this code",
           "explain the program", "explain my code",)

_FIX    = ("fix code", "fix the code", "debug code", "debug the code",
           "fix the program", "fix my code", "debug my code",)

_LIST   = ("list my codes", "list codes", "what codes", "show my codes",
           "what have you written", "what programs",)

_OPEN   = ("open code", "open the code", "open the program",
           "show the code",)


# ── Main handler ───────────────────────────────────────────

def handle_code(command: str) -> bool:
    c = command.lower().strip()

    # Explicit trigger word OR natural language code request
    if not (any(t in c for t in TRIGGERS) or _is_code_request(c)):
        return False

    CODE_DIR.mkdir(parents=True, exist_ok=True)

    # ── LIST ───────────────────────────────────────────────
    if any(t in c for t in _LIST):
        files = _all_files()
        if not files:
            speak("Nova Code Helper is empty. Ask me to write some code to get started.")
            return True
        speak(f"You have {len(files)} code file{'s' if len(files) != 1 else ''} "
              f"in Nova Code Helper.")
        for i, f in enumerate(files[:6], 1):
            lang = f.suffix[1:].upper() or "CODE"
            speak(f"{i}. {f.stem.replace('_', ' ')} — {lang}")
        if len(files) > 6:
            speak(f"And {len(files) - 6} more.")
        return True


    # ── WRITE ──────────────────────────────────────────────
    # Matches explicit write triggers AND natural phrases like
    # "create an HTML page", "build a calculator in Python"
    is_write_request = any(t in c for t in _WRITE) or (
        _is_code_request(c) and
        not any(t in c for t in _RUN + _EXPLAIN + _FIX + _LIST + _OPEN)
    )
    if is_write_request:
        task = c
        for filler in sorted(_WRITE, key=len, reverse=True):
            task = task.replace(filler, "")
        task = task.strip().strip(".,!?")

        if not task:
            speak("What would you like me to code?")
            return True

        ext, lang, runner = _detect_language(task)
        stem     = _sanitize_name(task)
        stamp    = datetime.now().strftime("%H%M%S")
        filename = f"{stem}_{stamp}{ext}"
        fpath    = CODE_DIR / filename

        speak(f"Writing {lang} code for {task}.")

        try:
            from core.engine import raw_query
            code = raw_query(
                f"Write clean, well-commented {lang} code for the following task:\n"
                f"Task: {task}\n\n"
                f"Language: {lang}\n"
                f"Requirements:\n"
                f"  - Complete, runnable, production-quality code\n"
                f"  - Meaningful variable/function names\n"
                f"  - Comments explaining logic at key steps\n"
                f"  - Graceful error handling and edge cases\n"
                f"  - Python: include main() + if __name__ == '__main__' with example\n"
                f"  - HTML: full document with embedded CSS, clean modern styling\n"
                f"  - JavaScript: include console.log example usage at bottom\n",
                fallback_order=["gemini", "ollama"],   # ← Groq saved for chat
            )

            # Strip any accidental markdown fences from the response
            code = re.sub(r"^```[\w]*\n?", "", code.strip())
            code = re.sub(r"\n?```$", "", code.strip())

            fpath.write_text(code, encoding="utf-8")
            log.info(f"[Code] Written: {fpath}")
            _open_in_editor(fpath)

            speak(
                f"Done. Saved {filename} to Nova Code Helper "
                f"and opened it in your editor."
            )

        except Exception as e:
            log.error(f"[Code Write Error] {e}")
            speak("Sorry, I couldn't write that code.")

        return True

    # ── RUN ────────────────────────────────────────────────
    if any(t in c for t in _RUN):
        hint = c
        for t in sorted(_RUN, key=len, reverse=True):
            hint = hint.replace(t, "")
        hint = hint.strip().strip(".,!?")

        fpath = _find_file(hint)
        if not fpath:
            _speak_files_available(_all_files())
            return True

        if fpath.suffix != ".py":
            speak(f"{fpath.name} is a {fpath.suffix[1:].upper()} file. "
                  f"I can only run Python files right now.")
            return True

        speak(f"Running {fpath.stem.replace('_', ' ')}.")
        try:
            result = subprocess.run(
                [sys.executable, str(fpath)],
                capture_output=True, text=True, timeout=30,
                cwd=str(CODE_DIR)
            )
            raw    = (result.stdout + result.stderr).strip()
            lines  = raw.splitlines() if raw else []

            if not lines:
                speak("Script ran successfully with no output.")
            elif len(lines) <= 4:
                speak(f"Output: {' '.join(lines)}")
            else:
                speak(
                    f"Script ran. {len(lines)} lines of output. "
                    f"First line: {lines[0]}. "
                    f"Last line: {lines[-1]}."
                )

        except subprocess.TimeoutExpired:
            speak("The script took too long and was stopped after 30 seconds.")
        except Exception as e:
            log.error(f"[Code Run Error] {e}")
            speak("Couldn't run that script.")

        return True

    # ── EXPLAIN ────────────────────────────────────────────
    if any(t in c for t in _EXPLAIN):
        hint = c
        for t in sorted(_EXPLAIN, key=len, reverse=True):
            hint = hint.replace(t, "")
        hint = hint.strip().strip(".,!?")

        fpath = _find_file(hint)
        if not fpath:
            _speak_files_available(_all_files())
            return True

        content = fpath.read_text(encoding="utf-8", errors="ignore")
        speak(f"Explaining {fpath.stem.replace('_', ' ')}.")

        try:
            from core.engine import raw_query
            explanation = raw_query(
                f"Explain what this {fpath.suffix[1:].upper()} code does.\n"
                f"Rules: max 3 sentences, spoken aloud, no markdown, no bullet points.\n"
                f"Focus on WHAT it does and WHY — not line-by-line syntax.\n\n"
                f"{content[:3000]}",
                system="You are a code explainer. Give a brief spoken explanation only.",
                fallback_order=["gemini", "ollama"],   # ← add this
            )
            speak(explanation)
        except Exception as e:
            log.error(f"[Code Explain Error] {e}")
            speak("Couldn't explain that code.")

        return True

    # ── FIX / DEBUG ────────────────────────────────────────
    if any(t in c for t in _FIX):
        hint = c
        for t in sorted(_FIX, key=len, reverse=True):
            hint = hint.replace(t, "")
        hint = hint.strip().strip(".,!?")

        fpath = _find_file(hint)
        if not fpath:
            _speak_files_available(_all_files())
            return True

        content = fpath.read_text(encoding="utf-8")
        speak(f"Fixing {fpath.stem.replace('_', ' ')}.")

        try:
            from core.engine import raw_query
            fixed = raw_query(
                f"Fix ALL bugs in this {fpath.suffix[1:].upper()} code.\n"
                f"Also improve: error handling, edge cases, code quality.\n"
                f"Return ONLY the fixed code. No explanation:\n\n{content}",
                fallback_order=["gemini", "ollama"],   # ← add this
            )

            # Strip markdown fences if present
            fixed = re.sub(r"^```[\w]*\n?", "", fixed.strip())
            fixed = re.sub(r"\n?```$", "", fixed.strip())

            # Backup original before overwriting
            backup = CODE_DIR / (fpath.stem + "_backup" + fpath.suffix)
            backup.write_text(content, encoding="utf-8")

            fpath.write_text(fixed, encoding="utf-8")
            log.info(f"[Code] Fixed: {fpath} (backup: {backup.name})")
            _open_in_editor(fpath)

            speak(
                f"Done. Fixed code saved to {fpath.name}. "
                f"Original backed up as {backup.name}. Opening the fixed version."
            )

        except Exception as e:
            log.error(f"[Code Fix Error] {e}")
            speak("Couldn't fix that code.")

        return True

    # ── OPEN ───────────────────────────────────────────────
    if any(t in c for t in _OPEN):
        hint = c
        for t in sorted(_OPEN, key=len, reverse=True):
            hint = hint.replace(t, "")
        hint = hint.strip().strip(".,!?")

        fpath = _find_file(hint)
        if not fpath:
            _speak_files_available(_all_files())
            return True

        _open_in_editor(fpath)
        speak(f"Opening {fpath.stem.replace('_', ' ')}.")
        return True

    return False