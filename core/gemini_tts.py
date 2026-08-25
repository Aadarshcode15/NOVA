# core/gemini_tts.py
import base64
import re
import time
import wave
import tempfile
import threading
from datetime import datetime
from config.settings import GEMINI_API_KEY, GEMINI_TTS_MODEL, NOVA_VOICE, SORA_VOICE
from core.logger import log

# ── Per-day budget tracking ───────────────────────────────
# Free tier = 10 calls/day. Track usage so we don't waste quota on
# non-essential sentences and preserve it for the responses that matter.
_lock          = threading.Lock()
_day_key: str  = ""          # "YYYY-MM-DD"
_day_count: int = 0
_DAY_BUDGET    = 9           # leave 1 in reserve; adjust upward if on paid tier

# ── Circuit breaker ───────────────────────────────────────
# After a 429, respect the retryDelay Google tells us (not a fixed 60s).
_cooldown_until: float = 0.0
_consecutive_fails: int = 0
_MAX_FAILS = 3


def _circuit_open() -> bool:
    with _lock:
        return time.time() < _cooldown_until


def _record_failure(error_str: str = "") -> None:
    global _consecutive_fails, _cooldown_until
    # Parse retry delay from Google's error message if present
    delay = 60.0
    match = re.search(r"retryDelay['\": ]+(\d+)", error_str)
    if match:
        delay = float(match.group(1)) + 5.0
    else:
        # Also check the RetryInfo details block format
        match2 = re.search(r"retry_delay.*?seconds.*?(\d+)", error_str, re.IGNORECASE)
        if match2:
            delay = float(match2.group(1)) + 5.0
    log.warning(f"[GeminiTTS] Rate limited — waiting {delay:.0f}s before retry.")
    with _lock:
        _consecutive_fails += 1
        if _consecutive_fails >= _MAX_FAILS:
            _cooldown_until = time.time() + delay
            log.warning(
                f"[GeminiTTS] {_MAX_FAILS} failures — pausing {delay:.0f}s, "
                f"Kokoro/Edge takes over."
            )


def _record_success() -> None:
    global _consecutive_fails, _day_count, _day_key
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        _consecutive_fails = 0
        if _day_key != today:
            _day_key   = today
            _day_count = 0
        _day_count += 1


def _budget_available() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        if _day_key != today:
            return True          # new day, fresh budget
        remaining = _DAY_BUDGET - _day_count
        if remaining <= 0:
            log.debug(f"[GeminiTTS] Daily budget exhausted ({_day_count}/{_DAY_BUDGET}), using local TTS.")
        return remaining > 0


def _voice_for(assistant: str) -> str:
    return NOVA_VOICE if assistant == "nova" else SORA_VOICE


def synthesize(text: str, assistant: str = "nova") -> str | None:
    """
    Calls Gemini TTS. Returns path to a playable WAV file, or None on failure.
    None signals the caller to fall back to Kokoro/Edge TTS.
    """
    if not GEMINI_API_KEY:
        return None
    if _circuit_open():
        return None
    if not _budget_available():
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        voice  = _voice_for(assistant)

        response = client.models.generate_content(
            model=GEMINI_TTS_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                    )
                ),
            ),
        )

        candidates = response.candidates
        if not candidates or not candidates[0].content.parts:
            raise ValueError("Empty response from Gemini TTS")

        part = candidates[0].content.parts[0]
        if not getattr(part, "inline_data", None) or not part.inline_data.data:
            raise ValueError("No audio data in response")

        raw = part.inline_data.data
        pcm = base64.b64decode(raw) if isinstance(raw, str) else raw

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            tmp_path = f.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm)

        _record_success()
        log.debug(f"[GeminiTTS] ✓ {voice} | {len(pcm)} bytes | day:{_day_count}/{_DAY_BUDGET}")
        return tmp_path

    except Exception as e:
        err_str = str(e)
        _record_failure(err_str)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            # Extract and log the actual wait time
            match = re.search(r"retryDelay.*?(\d+)s", err_str)
            wait  = match.group(1) if match else "unknown"
            log.warning(f"[GeminiTTS] Quota hit — retry in {wait}s. Falling back to local TTS.")
        else:
            log.warning(f"[GeminiTTS] Failed: {e}")
        return None