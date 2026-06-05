# core/engine.py
import threading
from collections import deque
from config.settings import (
    Engine, DEFAULT_ENGINE,
    GEMINI_API_KEY, GEMINI_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    OLLAMA_HOST, OLLAMA_MODEL,
)
from core.prompt import build_prompt


# ── Active State ───────────────────────────────────────────
_active_engine    = DEFAULT_ENGINE
_active_assistant = "nova"

def get_engine()    -> str: return _active_engine
def get_assistant() -> str: return _active_assistant

def set_engine(engine: str) -> None:
    global _active_engine
    if engine in (Engine.GEMINI, Engine.GROQ, Engine.OLLAMA):
        _active_engine = engine
        print(f"[Engine] Switched to {engine.upper()}")

def set_assistant(name: str) -> None:
    global _active_assistant
    if name.lower() in ("nova", "sora"):
        _active_assistant = name.lower()
        clear_history()   # fresh context when switching assistant
        print(f"[Engine] Active assistant: {_active_assistant.upper()}")

def toggle_assistant() -> str:
    new = "sora" if _active_assistant == "nova" else "nova"
    set_assistant(new)
    return new


# ── Conversation History ────────────────────────────────────
# Stores last 20 turns (10 user + 10 assistant).
# Thread-safe — audio loop and CommandWorker both call query().

_history_lock = threading.Lock()
_conversation_history: deque = deque(maxlen=20)

def add_to_history(role: str, content: str) -> None:
    """role must be 'user' or 'assistant'."""
    with _history_lock:
        _conversation_history.append({"role": role, "content": content})

def get_history() -> list:
    with _history_lock:
        return list(_conversation_history)

def clear_history() -> None:
    with _history_lock:
        _conversation_history.clear()


# ── Prompt Builders ────────────────────────────────────────

def _build_messages(assistant: str) -> list:
    """
    OpenAI-style messages list for Groq and Ollama.
    The current user turn is already in history when this is called,
    so history gives us: [...past turns..., current user message].
    """
    messages = [{"role": "system", "content": build_prompt(assistant)}]
    for turn in get_history():
        messages.append(turn)
    return messages


def _build_gemini_prompt(text: str, assistant: str) -> str:
    """
    Text-format prompt for Gemini, with recent history prepended.
    Excludes the current user message from history (re-appends as 'User: {text}').
    """
    history = get_history()
    past    = history[:-1]        # exclude the current user turn we just added
    recent  = past[-6:] if past else []   # last 3 exchanges to stay within tokens

    if not recent:
        return f"{build_prompt(assistant)}\n\nUser: {text}"

    history_text = "\n".join([
        f"User: {m['content']}" if m["role"] == "user" else f"Assistant: {m['content']}"
        for m in recent
    ])
    return f"{build_prompt(assistant)}\n\n{history_text}\nUser: {text}"


# ── Engine Backends ────────────────────────────────────────

def _query_gemini(text: str, assistant: str) -> str:
    from google import genai
    client   = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model    = GEMINI_MODEL,
        contents = _build_gemini_prompt(text, assistant),
    )
    return response.text.strip()


def _query_groq(text: str, assistant: str) -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    resp   = client.chat.completions.create(
        model    = GROQ_MODEL,
        messages = _build_messages(assistant),
    )
    return resp.choices[0].message.content.strip()


def _query_ollama(text: str, assistant: str) -> str:
    from ollama import Client as OllamaClient
    client = OllamaClient(host=OLLAMA_HOST)
    resp   = client.chat(
        model    = OLLAMA_MODEL,
        messages = _build_messages(assistant),
    )
    return resp["message"]["content"].strip()


# ── Gemini Vision (no history needed) ─────────────────────

def query_vision(image_b64: str, prompt: str) -> str:
    try:
        from google import genai
        from google.genai import types
        import base64
        client   = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model    = GEMINI_MODEL,
            contents = [
                types.Part.from_bytes(
                    data      = base64.b64decode(image_b64),
                    mime_type = "image/png"
                ),
                prompt
            ]
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Vision Error] {e}")
        return "Vision analysis failed."


# ── Fallback Chain ─────────────────────────────────────────
# On any failure, tries the next engine automatically.
# User hears a clean response — never a raw exception string.

_FALLBACK_CHAIN = {
    Engine.GEMINI: [Engine.GEMINI, Engine.GROQ,   Engine.OLLAMA],
    Engine.GROQ:   [Engine.GROQ,   Engine.GEMINI, Engine.OLLAMA],
    Engine.OLLAMA: [Engine.OLLAMA, Engine.GROQ,   Engine.GEMINI],
}

_ENGINE_FN = {
    Engine.GEMINI: _query_gemini,
    Engine.GROQ:   _query_groq,
    Engine.OLLAMA: _query_ollama,
}


# ── Main Query Entry Point ─────────────────────────────────

def query(text: str, assistant: str = None, engine: str = None) -> str:
    """
    Send text to the AI with full conversation history.
    Falls back through the engine chain silently on any error.

    History flow:
      1. User turn added to history   ← before calling engine
      2. Engine builds prompt/messages from history
      3. Response added to history    ← after engine returns
    """
    asst = (assistant or _active_assistant).lower()
    eng  = (engine    or _active_engine).lower()

    # Step 1 — record user turn so history builders see it
    add_to_history("user", text)

    print(f"[Engine] {eng.upper()} | {asst.upper()} ← {text[:60]}")

    # Step 2 — try preferred engine, fall back on failure
    response = None
    for attempt in _FALLBACK_CHAIN.get(eng, [eng]):
        try:
            fn     = _ENGINE_FN.get(attempt)
            result = fn(text, asst)
            if result and result.strip():
                if attempt != eng:
                    print(f"[Engine] Fell back to {attempt.upper()}")
                response = result
                break
        except Exception as e:
            print(f"[Engine] {attempt.upper()} failed: {e}")
            continue

    if not response:
        response = "I am having trouble connecting right now. Please try again."

    # Step 3 — record assistant response
    add_to_history("assistant", response)

    return response