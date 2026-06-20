# core/stt_engine.py
import threading
import numpy as np
import speech_recognition as sr
from core.logger import log

# ── Model config ───────────────────────────────────────────
# Accuracy/speed tradeoff:
#   small.en       ~1.5s   — fast, decent accuracy        (previous)
#   medium.en      ~3-4s   — noticeably more accurate
#   large-v3-turbo ~3-5s   — best accuracy, distilled for speed   ← current
# Groq API handles accuracy online — local model is offline fallback only.
# small.en is fast enough for that role.
_MODEL_SIZE    = "small.en"   # local offline fallback
_COMPUTE_TYPE  = "int8"
_DEVICE        = "cpu"

# ── NOVA vocabulary prompt ─────────────────────────────────
# Primes Whisper with the vocabulary it will commonly hear.
# Dramatically reduces misheard app names, command words, proper nouns.
# Update CONTACT_NAMES with your actual contacts for best results.

CONTACT_NAMES = "Raj, Priya, Amit, Rohan, Ananya, AG"  # ← add your contacts here

_NOVA_PROMPT = (
    f"NOVA voice assistant. Mumbai, India. "
    f"Commands: open Chrome, open Spotify, open WhatsApp, open VS Code, "
    f"open Discord, open YouTube, open Notepad, open Calculator, "
    f"play music, pause music, next song, previous song, volume up, volume down, "
    f"set volume to fifty, set brightness to seventy, take a screenshot, "
    f"what is the weather, what time is it, what is the date, check battery, "
    f"search on YouTube, play on YouTube, summarize video, "
    f"remind me to, set a reminder, add to my to-do list, show my tasks, "
    f"send WhatsApp message to {CONTACT_NAMES}, "
    f"write code, run code, explain code, fix code, "
    f"search for, what is, who is, how to, tell me about, "
    f"switch to Gemini, switch to Groq, switch to Ollama, "
    f"remember that, what do you know about me, "
    f"morning briefing, daily briefing, give me my briefing, "
    f"run the briefing, start briefing, "
    f"check my emails, read my emails, any new emails, unread emails, "
    f"send email to, summarize that email, emails from, "
    f"what's on my calendar, my calendar today, my schedule, "
    f"add to my calendar, create an event, schedule a meeting, "
    f"create a portfolio, create a website, build a calculator, "
    f"write a program, write a script, list my codes."
    f"browse to, search Amazon for, search Flipkart for, "
    f"search LinkedIn for, find jobs on LinkedIn, close the browser, "
    f"what's on this page, summarize this page, click on, click the."
)

_model      = None
_model_lock = threading.Lock()


# ── Model loading ──────────────────────────────────────────

def load_model() -> bool:
    global _model
    with _model_lock:
        if _model is not None:
            return True

        from faster_whisper import WhisperModel

        # ── Try the primary model first ──
        try:
            log.info(f"[STT] Loading faster-whisper '{_MODEL_SIZE}' ({_COMPUTE_TYPE})...")
            _model = WhisperModel(
                _MODEL_SIZE,
                device       = _DEVICE,
                compute_type = _COMPUTE_TYPE,
            )
            log.info(f"[STT] Whisper ready ({_MODEL_SIZE}).")
            return True
        except Exception as e:
            log.warning(f"[STT] '{_MODEL_SIZE}' unavailable ({e}). "
                       f"Falling back to '{_FALLBACK_SIZE}'...")

        # ── Fallback if turbo isn't supported by this faster-whisper version ──
        try:
            _model = WhisperModel(
                _FALLBACK_SIZE,
                device       = _DEVICE,
                compute_type = _COMPUTE_TYPE,
            )
            log.info(f"[STT] Whisper ready (fallback: {_FALLBACK_SIZE}).")
            return True
        except Exception as e:
            log.error(f"[STT] Both models failed to load: {e}")
            return False


def preload() -> None:
    """Pre-load model in background so first command isn't delayed."""
    threading.Thread(target=load_model, daemon=True, name="Whisper-Loader").start()


def is_ready() -> bool:
    return _model is not None


# ── Audio conversion ───────────────────────────────────────

def _to_numpy(audio: sr.AudioData) -> np.ndarray:
    """Convert sr.AudioData → float32 numpy array at 16 kHz."""
    wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
    samples   = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32)
    return samples / 32768.0


# ── Hallucination filter ───────────────────────────────────

_HALLUCINATIONS = frozenset({
    "", ".", "..", "...", "you", "thank you", "thanks",
    "thank you.", "thanks.", "bye", "bye.", "okay", "ok",
    "thank you for watching.", "thanks for watching.",
    "please subscribe.", "like and subscribe.",
})

def _is_repetitive(text: str) -> bool:
    """Detect looping hallucination — 'X. X. X. X.' pattern."""
    words = text.split()
    if len(words) < 12:
        return False
    chunk     = max(4, len(words) // 3)
    first     = " ".join(words[:chunk]).lower()
    remainder = " ".join(words[chunk:]).lower()
    return first in remainder

def _transcribe_groq(audio: sr.AudioData) -> str:
    """
    Transcribe using Groq's hosted Whisper large-v3-turbo API.
    ~0.5s latency, large-v3-turbo accuracy, uses existing GROQ_API_KEY.
    No new API key or account needed.
    Returns empty string on any failure so caller falls back to local.
    """
    import os
    import tempfile
    from groq import Groq
    from config.settings import GROQ_API_KEY

    if not GROQ_API_KEY:
        return ""

    # Convert AudioData → WAV bytes at 16kHz
    wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)

    # Must be at least 0.5s of audio or Groq rejects it
    if len(wav_bytes) < 16000:
        return ""

    # Write to temp file — Groq API requires a file object
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name

        client = Groq(api_key=GROQ_API_KEY)
        with open(tmp_path, "rb") as f:
            result = client.audio.transcriptions.create(
                file            = ("audio.wav", f.read()),
                model           = "whisper-large-v3-turbo",
                language        = "en",
                prompt          = _NOVA_PROMPT,   # same vocab hint as local model
                response_format = "text",         # returns plain string directly
            )

        text = result.strip() if isinstance(result, str) else getattr(result, "text", "").strip()
        if text:
            log.debug(f"[STT] Groq Whisper: '{text}'")
        return text

    except Exception as e:
        log.debug(f"[STT] Groq Whisper unavailable: {e}")
        return ""
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

# ── Main transcription ─────────────────────────────────────

def transcribe(audio: sr.AudioData) -> str:
    """
    Transcription priority chain:
      1. Groq Whisper API  — fast (~0.5s), large-v3-turbo accuracy
      2. Local faster-whisper — offline fallback (small.en, ~1.5s)
      3. Caller falls back to Google STT if we return ""

    Hallucination filters applied regardless of which path ran.
    """
    # ── 1. Groq API ───────────────────────────────────────
    text = _transcribe_groq(audio)
    if text:
        # Still apply filters — Groq can also hallucinate on silence
        if text.lower().rstrip(".!? ") in _HALLUCINATIONS:
            log.debug(f"[STT] Groq hallucination filtered: '{text}'")
            return ""
        if len(text.split()) > 20:
            log.debug(f"[STT] Groq: rejected long output ({len(text.split())} words)")
            return ""
        if _is_repetitive(text):
            log.debug(f"[STT] Groq: rejected repetitive output")
            return ""
        log.info(f"[STT] Groq ✓ '{text}'")
        return text

    # ── 2. Local faster-whisper ───────────────────────────
    log.debug("[STT] Groq unavailable — using local Whisper")

    global _model
    if _model is None:
        if not load_model():
            return ""

    try:
        audio_np = _to_numpy(audio)
        if len(audio_np) < 8000:
            return ""

        with _model_lock:
            segments, info = _model.transcribe(
                audio_np,
                language                   = "en",
                beam_size                  = 5,
                vad_filter                 = True,
                vad_parameters             = dict(
                    min_silence_duration_ms = 400,
                    speech_pad_ms           = 300,
                ),
                condition_on_previous_text = False,
                temperature                = 0.0,
                initial_prompt             = _NOVA_PROMPT,
            )

        parts = []
        for seg in segments:
            if seg.avg_logprob < -0.8:
                continue
            if seg.no_speech_prob > 0.7:
                continue
            parts.append(seg.text.strip())

        text = " ".join(parts).strip()

        if text.lower().rstrip(".!? ") in _HALLUCINATIONS:
            return ""
        if len(text.split()) > 20:
            return ""
        if _is_repetitive(text):
            return ""

        if text:
            log.info(f"[STT] Local ✓ '{text}'")
        return text

    except Exception as e:
        log.error(f"[STT] Local Whisper error: {e}")
        return ""