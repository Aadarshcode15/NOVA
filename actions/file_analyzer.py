# actions/file_analyzer.py
import base64
import threading
from pathlib import Path
from core.logger import log
from core.voice import speak
from core.engine import raw_query, query_vision_groq

# ── Session state ──────────────────────────────────────────
# Tracks the currently loaded file across commands.
# "summarize it" / "explain it" always refers to this file.

_active: dict = {
    "path":    None,   # Path object
    "type":    None,   # "image" | "pdf" | "code" | "text"
    "name":    "",
    "content": "",     # extracted text (for non-image files)
    "lang":    "",     # programming language (for code files)
}

def get_active() -> dict:
    return _active

def has_active_file() -> bool:
    return _active["path"] is not None


# ── File type detection ────────────────────────────────────

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
_CODE_EXT  = {".py", ".js", ".ts", ".html", ".css", ".java",
              ".cpp", ".c", ".go", ".rb", ".sql", ".sh", ".kt"}
_TEXT_EXT  = {".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml"}
_PDF_EXT   = {".pdf"}

_LANG_NAMES = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".html": "HTML", ".css": "CSS", ".java": "Java",
    ".cpp": "C++", ".c": "C", ".go": "Go", ".rb": "Ruby",
    ".sql": "SQL", ".sh": "Bash", ".kt": "Kotlin",
}

def _detect_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in _IMAGE_EXT: return "image"
    if ext in _PDF_EXT:   return "pdf"
    if ext in _CODE_EXT:  return "code"
    if ext in _TEXT_EXT:  return "text"
    return "unknown"


# ── Content extractors ─────────────────────────────────────

def _read_pdf(path: Path) -> tuple:
    """Returns (text, page_count)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages  = len(reader.pages)
        text   = ""
        for page in reader.pages[:20]:   # cap at 20 pages for memory
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text.strip(), pages
    except Exception as e:
        log.error(f"[FileAnalyzer] PDF read error: {e}")
        return "", 0


def _read_code(path: Path) -> tuple:
    """Returns (code_text, line_count, language)."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        lines   = len(content.splitlines())
        lang    = _LANG_NAMES.get(path.suffix.lower(), path.suffix[1:].upper())
        return content, lines, lang
    except Exception as e:
        log.error(f"[FileAnalyzer] Code read error: {e}")
        return "", 0, "code"


def _read_text(path: Path) -> tuple:
    """Returns (text, word_count)."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        words   = len(content.split())
        return content, words
    except Exception as e:
        log.error(f"[FileAnalyzer] Text read error: {e}")
        return "", 0


# ── On-upload announcement ─────────────────────────────────

def load_and_announce(filepath: str) -> None:
    """
    Called in a background thread when user uploads a file.
    Detects type, extracts content, announces to user, and for
    images runs vision immediately.
    """
    global _active
    path     = Path(filepath)
    filetype = _detect_type(path)

    # Reset active file
    _active = {
        "path":    path,
        "type":    filetype,
        "name":    path.name,
        "content": "",
        "lang":    "",
    }

    log.info(f"[FileAnalyzer] Loaded: {path.name} ({filetype})")

    # ── IMAGE — run vision immediately ──────────────────────
    if filetype == "image":
        speak(f"Let me take a look at {path.name}.")
        try:
            with open(path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            description = query_vision_groq(
                img_b64,
                "Describe what you see in this image in 2 to 3 clear spoken sentences. "
                "Be specific. No markdown, no bullet points."
            )
            speak(description)
            speak("Say 'describe it in more detail' if you want more, "
                  "or ask me anything about this image.")
            _active["content"] = description
        except Exception as e:
            log.error(f"[FileAnalyzer] Vision error: {e}")
            speak(f"I loaded {path.name} but couldn't analyse it. "
                  "Make sure it is a valid image file.")
        return

    # ── PDF ─────────────────────────────────────────────────
    if filetype == "pdf":
        text, pages = _read_pdf(path)
        _active["content"] = text
        if pages == 0:
            speak(f"I loaded {path.name} but couldn't read the text. "
                  "It may be a scanned or image-based PDF.")
            return
        preview = text[:120].replace("\n", " ").strip()
        speak(
            f"Loaded {path.name} — {pages} page{'s' if pages > 1 else ''}. "
            f"It starts with: {preview}... "
            f"Say 'summarize it' to get the key points."
        )
        return

    # ── CODE ─────────────────────────────────────────────────
    if filetype == "code":
        content, lines, lang = _read_code(path)
        _active["content"] = content
        _active["lang"]    = lang
        speak(
            f"Loaded {path.name} — {lang} file, {lines} lines. "
            f"Say 'explain it' to understand what it does, "
            f"or 'fix it' to debug any issues."
        )
        return

    # ── TEXT ─────────────────────────────────────────────────
    if filetype == "text":
        content, words = _read_text(path)
        _active["content"] = content
        speak(
            f"Loaded {path.name} — {words} words. "
            f"Say 'summarize it' for a quick overview, "
            f"or ask me anything about it."
        )
        return

    # ── Unknown ──────────────────────────────────────────────
    speak(
        f"I loaded {path.name}. "
        f"I can work with images, PDFs, code files, and text files. "
        f"This type might not be fully supported."
    )


# ── File command handler ───────────────────────────────────

_SUMMARIZE = (
    "summarize it", "summarize the file", "summarize this",
    "give me a summary", "what does it say", "what's in it",
    "sum it up", "give me the gist", "what is this about",
    "what's this file about",
)

_EXPLAIN = (
    "explain it", "explain the code", "what does this code do",
    "what does it do", "break it down", "describe the code",
    "what is this code", "walk me through it",
)

_DETAIL = (
    "more detail", "tell me more", "describe it in more detail",
    "go deeper", "expand on that",
)


def handle_file_command(command: str) -> bool:
    """
    Route to file handler if a file is loaded and the command
    matches a file-action pattern.
    Called from command_router BEFORE the AI fallback.
    """
    if not has_active_file():
        return False

    c    = command.lower().strip()
    name = _active["name"]
    typ  = _active["type"]
    content = _active["content"]

    # ── Summarize ───────────────────────────────────────────
    if any(t in c for t in _SUMMARIZE):
        if not content:
            speak(f"I couldn't extract text from {name}. "
                  "It may be a scanned or protected file.")
            return True

        speak(f"Summarizing {name}.")
        try:
            summary = raw_query(
                f"Summarize the following document in 3 concise spoken sentences. "
                f"Focus on the main topic and most important points. "
                f"No markdown, no bullet points:\n\n{content[:4000]}",
                system=(
                    "You are a document summarizer for a voice assistant. "
                    "Return only a brief spoken summary. No formatting."
                )
            )
            speak(summary)
        except Exception as e:
            log.error(f"[FileAnalyzer] Summarize error: {e}")
            speak("I couldn't summarize that file right now.")
        return True

    # ── Explain code ────────────────────────────────────────
    if any(t in c for t in _EXPLAIN):
        if typ != "code":
            speak(f"{name} is not a code file. Say 'summarize it' instead.")
            return True
        if not content:
            speak("I couldn't read the code file.")
            return True

        lang = _active.get("lang", "code")
        speak(f"Explaining the {lang} code.")
        try:
            explanation = raw_query(
                f"Explain what this {lang} code does in 3 spoken sentences. "
                f"Focus on WHAT it does and WHY, not the syntax. "
                f"No markdown, no bullet points:\n\n{content[:3000]}",
                system=(
                    "You are a code explainer for a voice assistant. "
                    "Be clear, concise, and jargon-free."
                )
            )
            speak(explanation)
        except Exception as e:
            log.error(f"[FileAnalyzer] Explain error: {e}")
            speak("I couldn't explain that code right now.")
        return True

    # ── More detail on image ─────────────────────────────────
    if any(t in c for t in _DETAIL) and typ == "image":
        speak("Let me look more carefully.")
        try:
            with open(_active["path"], "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            detail = query_vision_groq(
                img_b64,
                "Give a detailed description of this image. "
                "Include text visible in the image, colours, layout, and any important details. "
                "3 to 4 sentences, no markdown."
            )
            speak(detail)
        except Exception as e:
            log.error(f"[FileAnalyzer] Detail vision error: {e}")
            speak("Couldn't get more detail right now.")
        return True

    # ── Pass-through: send file content as context to AI ────
    # For any other question about the file (e.g. "who wrote this?")
    if any(k in c for k in ("this file", "the file", "this document",
                             "the document", "this code", "the code",
                             "this image", "the image", "it", "this")):
        if content:
            from core.engine import query
            response = query(
                f"The user has loaded a file called '{name}'. "
                f"Here is its content:\n\n{content[:3000]}\n\n"
                f"User question: {command}",
                skip_history=True
            )
            speak(response)
            return True

    return False