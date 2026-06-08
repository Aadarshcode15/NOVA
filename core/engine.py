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
from core.logger import log


# ── Active State ───────────────────────────────────────────
_active_engine    = DEFAULT_ENGINE
_active_assistant = "nova"

def get_engine()    -> str: return _active_engine
def get_assistant() -> str: return _active_assistant

def set_engine(engine: str) -> None:
    global _active_engine, _manual_override
    if engine in (Engine.GEMINI, Engine.GROQ, Engine.OLLAMA):
        _active_engine    = engine
        _manual_override  = True    # user explicitly chose — pause smart routing
        log.info(f"[Engine] Switched to {engine.upper()} (manual — smart routing paused)")

def set_assistant(name: str) -> None:
    global _active_assistant
    if name.lower() in ("nova", "sora"):
        _active_assistant = name.lower()
        clear_history()   # fresh context when switching assistant
        log.info(f"[Engine] Active assistant → {_active_assistant.upper()} (history cleared)")

def toggle_assistant() -> str:
    new = "sora" if _active_assistant == "nova" else "nova"
    set_assistant(new)
    return new


# ── Conversation History ────────────────────────────────────
# Stores last 20 turns (10 user + 10 assistant).
# Thread-safe — audio loop and CommandWorker both call query().

_history_lock = threading.Lock()
_conversation_history: deque = deque(maxlen=20)

# ── Engine usage stats (current session) ──────────────────
# Tracks how many calls go to each engine.
# Lets you verify smart routing is saving Gemini calls.
_engine_stats: dict = {Engine.GEMINI: 0, Engine.GROQ: 0, Engine.OLLAMA: 0}
_manual_override: bool = False   # True when user explicitly switches engine


def get_engine_stats() -> dict:
    return dict(_engine_stats)


def log_engine_stats() -> None:
    total = sum(_engine_stats.values())
    if total == 0:
        return
    log.info(
        f"[Engine Stats] {total} total calls — "
        f"Gemini: {_engine_stats[Engine.GEMINI]} | "
        f"Groq: {_engine_stats[Engine.GROQ]} | "
        f"Ollama: {_engine_stats[Engine.OLLAMA]}"
    )

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

# ── Smart Engine Router ────────────────────────────────────

def _smart_select_engine(text: str, preferred: str) -> str:
    """
    Select the optimal engine for this query.

    Rules (in priority order):
      1. Explicit offline/local request     → Ollama
      2. Code / analysis / creation tasks  → Gemini  (needs depth)
      3. Long queries (> 15 words)          → Gemini  (complexity signal)
      4. Greetings / short chitchat         → Groq    (fast, saves Gemini quota)
      5. Short queries (≤ 8 words)          → Groq    (fast enough)
      6. Everything else                    → user preferred engine

    If user manually switched engine (set_engine() called), returns preferred
    immediately — manual choice always wins.
    """
    import re

    # Manual override — respect user's explicit choice
    if _manual_override:
        return preferred

    t = text.lower().strip()

    # ── 1. Explicit offline/private → Ollama ──────────────
    OFFLINE_SIGNALS = ("offline", "local mode", "use local", "go private",
                       "no internet", "use ollama")
    if any(k in t for k in OFFLINE_SIGNALS):
        return Engine.OLLAMA

    # ── 2. Complex tasks → Gemini ─────────────────────────
    GEMINI_PATTERNS = [
        r"\b(write|create|generate|draft|compose|build)\b",
        r"\b(explain|analyze|analyse|compare|evaluate|summarize|summarise)\b",
        r"\b(code|script|program|function|algorithm|debug|fix the)\b",
        r"\b(essay|letter|email|report|document|story|poem)\b",
        r"\b(why|how does|what causes|difference between|pros and cons)\b",
        r"\b(translate|convert|transform|refactor)\b",
        r"\b(step by step|in detail|thoroughly|in depth|walk me through)\b",
        r"\b(research|investigate|deep dive|breakdown)\b",
    ]
    for pattern in GEMINI_PATTERNS:
        if re.search(pattern, t):
            log.debug(f"[SmartRoute] Complex task detected → GEMINI")
            return Engine.GEMINI

    # ── 3. Long queries → Gemini ──────────────────────────
    if len(text.split()) > 15:
        log.debug(f"[SmartRoute] Long query ({len(text.split())} words) → GEMINI")
        return Engine.GEMINI

    # ── 4. Simple chitchat → Groq ─────────────────────────
    GROQ_PATTERNS = [
        r"^(hi|hello|hey|good\s+(morning|evening|night|afternoon))\b",
        r"^(how are you|what'?s up|how'?s it going|you good)\b",
        r"^(thanks|thank you|cheers|ok|okay|sure|got it|cool|great|awesome|nice)\b",
        r"^(tell me a joke|say something|make me laugh|be funny)\b",
        r"^(who are you|what are you|what can you do|introduce yourself)\b",
        r"^(yes|no|maybe|definitely|absolutely|of course|certainly)\b",
        r"^(good job|well done|nice work|perfect|excellent)\b",
    ]
    for pattern in GROQ_PATTERNS:
        if re.search(pattern, t):
            log.debug(f"[SmartRoute] Chitchat → GROQ")
            return Engine.GROQ

    # ── 5. Short queries → Groq ───────────────────────────
    if len(text.split()) <= 8:
        log.debug(f"[SmartRoute] Short query ({len(text.split())} words) → GROQ")
        return Engine.GROQ

    # ── 6. Default → user preferred ──────────────────────
    return preferred

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
        log.error(f"[Vision Error] {e}")
        return "Vision analysis failed."
    
def query_vision_groq(image_b64: str, prompt: str) -> str:
    """
    Vision query using Groq's Llama 4 Scout.
    Free tier, fast, no Gemini quota consumed.
    Falls back to Gemini Vision on failure.
    """
    from config.settings import GROQ_VISION_MODEL

    # ── Try Groq Vision first ──────────────────────────────
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp   = client.chat.completions.create(
            model      = GROQ_VISION_MODEL,
            messages   = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            max_tokens = 300,
        )
        result = resp.choices[0].message.content.strip()
        if result:
            log.info("[Vision] Groq vision used.")
            return result
    except Exception as e:
        log.warning(f"[Vision] Groq vision failed, falling back to Gemini: {e}")

    # ── Fallback to Gemini Vision ──────────────────────────
    return query_vision(image_b64, prompt)

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

# ── Raw Query — for code gen, summarization, internal tasks ──
# No conversation history, no persona, no memory bleed.
# Use this whenever the AI must return structured output (code, JSON, etc.)

_CODE_SYSTEM = (
    "You are an expert software developer and code generator.\n"
    "ABSOLUTE RULES — no exceptions:\n"
    "1. Return ONLY raw source code. Nothing else.\n"
    "2. NO markdown fences (no ``` or ```python or ```html)\n"
    "3. NO explanations, greetings, commentary, or personal messages\n"
    "4. NO references to the user or their interests\n"
    "5. Start the code on line 1, character 1\n"
    "6. Code must be complete, runnable, and well-commented\n"
)

def raw_query(prompt: str, system: str = _CODE_SYSTEM, engine: str = None,
              fallback_order: list = None) -> str:
    """
    Direct AI call with custom system prompt.
    Completely bypasses: conversation history, NOVA persona, user memory.
    Used for: code generation, document processing, structured output.

    fallback_order: custom engine chain e.g. ["gemini", "ollama"]
                    overrides the default chain for this call only.
    """
    eng   = (engine or _active_engine).lower()
    chain = fallback_order if fallback_order else _FALLBACK_CHAIN.get(eng, [eng])

    for attempt in chain:
        try:
            if attempt == Engine.GROQ:
                from groq import Groq
                client = Groq(api_key=GROQ_API_KEY)
                resp   = client.chat.completions.create(
                    model       = GROQ_MODEL,
                    messages    = [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt},
                    ],
                    temperature = 0.2,   # lower = more deterministic code
                )
                result = resp.choices[0].message.content.strip()

            elif attempt == Engine.GEMINI:
                from google import genai
                client   = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model    = GEMINI_MODEL,
                    contents = f"{system}\n\n{prompt}",
                )
                result = response.text.strip()

            elif attempt == Engine.OLLAMA:
                from ollama import Client as OllamaClient
                client = OllamaClient(host=OLLAMA_HOST)
                resp   = client.chat(
                    model    = OLLAMA_MODEL,
                    messages = [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt},
                    ],
                )
                result = resp["message"]["content"].strip()
            else:
                continue

            if result:
                if attempt != eng:
                    log.warning(f"[Engine] raw_query fell back to {attempt.upper()}")
                log.info(f"[Engine] raw_query via {attempt.upper()} ({len(result)} chars)")
                return result

        except Exception as e:
            log.error(f"[Engine] raw_query {attempt.upper()} failed: {e}")
            continue

    return ""

# ── Main Query Entry Point ─────────────────────────────────

def query(text: str, assistant: str = None, engine: str = None,
          skip_history: bool = False) -> str:
    asst      = (assistant or _active_assistant).lower()
    preferred = (engine    or _active_engine).lower()

    # ── Smart engine selection ─────────────────────────────
    eng = _smart_select_engine(text, preferred)

    # Step 1 — record user turn (skip for internal action handler calls)
    if not skip_history:
        add_to_history("user", text)

    # Track usage stats
    if eng in _engine_stats:
        _engine_stats[eng] += 1

    if eng != preferred:
        log.info(f"[Engine] {preferred.upper()} → {eng.upper()} (smart route) | {text[:50]}")
    else:
        log.info(f"[Engine] {eng.upper()} | {asst.upper()} ← {text[:60]}")

    # Step 2 — try preferred engine, fall back on failure
    response = None
    for attempt in _FALLBACK_CHAIN.get(eng, [eng]):
        try:
            fn     = _ENGINE_FN.get(attempt)
            result = fn(text, asst)
            if result and result.strip():
                if attempt != eng:
                    log.warning(f"[Engine] Fell back to {attempt.upper()}")
                response = result
                break
        except Exception as e:
            log.error(f"[Engine] {attempt.upper()} failed: {e}")
            continue

    if not response:
        response = "I am having trouble connecting right now. Please try again."

# Step 3 — record assistant response (skip for internal calls)
    if not skip_history:
        add_to_history("assistant", response)

    return response