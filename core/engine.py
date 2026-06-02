# core/engine.py
import os
from config.settings import (
    Engine, DEFAULT_ENGINE,
    GEMINI_API_KEY, GEMINI_MODEL,
    GROQ_API_KEY, GROQ_MODEL,
    OLLAMA_HOST, OLLAMA_MODEL,
)
from core.prompt import build_prompt

# ── State ──────────────────────────────────────────────────
_active_engine   = DEFAULT_ENGINE
_active_assistant = "nova"   # "nova" or "sora"

def get_engine()     -> str: return _active_engine
def get_assistant()  -> str: return _active_assistant

def set_engine(engine: str) -> None:
    global _active_engine
    if engine in (Engine.GEMINI, Engine.GROQ, Engine.OLLAMA):
        _active_engine = engine
        print(f"[Engine] Switched to {engine.upper()}")

def set_assistant(name: str) -> None:
    global _active_assistant
    if name.lower() in ("nova", "sora"):
        _active_assistant = name.lower()
        print(f"[Engine] Active assistant: {_active_assistant.upper()}")

def toggle_assistant() -> str:
    new = "sora" if _active_assistant == "nova" else "nova"
    set_assistant(new)
    return new

# ── Gemini ─────────────────────────────────────────────────
def _query_gemini(text: str, assistant: str) -> str:
    try:
        from google import genai
        client   = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=f"{build_prompt(assistant)}\n\nUser: {text}",
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return f"Gemini error: {e}"
# ── Groq ───────────────────────────────────────────────────
def _query_groq(text: str, assistant: str) -> str:
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp   = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": build_prompt(assistant)},
                {"role": "user",   "content": text},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Groq Error] {e}")
        return f"Groq error: {e}"

# ── Ollama ─────────────────────────────────────────────────
def _query_ollama(text: str, assistant: str) -> str:
    try:
        from ollama import Client as OllamaClient
        client = OllamaClient(host=OLLAMA_HOST)
        resp   = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": build_prompt(assistant)},
                {"role": "user",   "content": text},
            ],
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        print(f"[Ollama Error] {e}")
        return "Ollama is not responding. Make sure it is running."

# ── Gemini Vision ───────────────────────────────────────────
def query_vision(image_b64: str, prompt: str) -> str:
    try:
        from google import genai
        from google.genai import types
        import base64
        client   = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(
                    data=base64.b64decode(image_b64),
                    mime_type="image/png"
                ),
                prompt
            ]
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Vision Error] {e}")
        return "Vision analysis failed."

# ── Main Query Entry Point ─────────────────────────────────
def query(text: str, assistant: str = None, engine: str = None) -> str:
    """
    Send text to the active AI engine.
    Optionally override assistant or engine for this call only.
    """
    asst = (assistant or _active_assistant).lower()
    eng  = (engine    or _active_engine).lower()

    print(f"[Engine] {eng.upper()} | {asst.upper()} ← {text[:60]}")

    if eng == Engine.GEMINI:
        return _query_gemini(text, asst)
    elif eng == Engine.GROQ:
        return _query_groq(text, asst)
    elif eng == Engine.OLLAMA:
        return _query_ollama(text, asst)
    else:
        return _query_gemini(text, asst)
