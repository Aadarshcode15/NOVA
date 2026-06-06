# core/stt_engine.py
import threading
import numpy as np
import speech_recognition as sr
from core.logger import log

# ── Model config ───────────────────────────────────────────
# tiny  =  39 MB  ~0.5s  — fastest, lower accuracy
# base  =  74 MB  ~0.8s  — fast, decent accuracy
# small = 461 MB  ~1.5s  — best balance  ← default
_MODEL_SIZE    = "small.en"  # English-only models are smaller + more accurate for English speech you can remove en suffix to get multilingual versions, but they may hallucinate Devanagari output for Hindi speech
_COMPUTE_TYPE  = "int8"      # quantised — faster + less RAM, same accuracy
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
    f"remember that, what do you know about me."
)

_model      = None
_model_lock = threading.Lock()


# ── Model loading ──────────────────────────────────────────

def load_model() -> bool:
    global _model
    with _model_lock:
        if _model is not None:
            return True
        try:
            from faster_whisper import WhisperModel
            log.info(f"[STT] Loading faster-whisper '{_MODEL_SIZE}' ({_COMPUTE_TYPE})...")
            _model = WhisperModel(
                _MODEL_SIZE,
                device       = _DEVICE,
                compute_type = _COMPUTE_TYPE,
            )
            log.info("[STT] Whisper ready.")
            return True
        except Exception as e:
            log.error(f"[STT] Failed to load Whisper: {e}")
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


# ── Main transcription ─────────────────────────────────────

def transcribe(audio: sr.AudioData) -> str:
    """
    Transcribe using faster-whisper.

    Key improvements over openai-whisper:
    - vad_filter: built-in silence detection — skips non-speech automatically
    - language="en": forces English output — prevents Devanagari/Romanised Hindi
    - avg_logprob filter: rejects low-confidence segments
    - 4x faster on CPU via int8 quantisation
    """
    global _model

    if _model is None:
        if not load_model():
            return ""

    try:
        audio_np = _to_numpy(audio)

        # Skip clips shorter than 0.5s
        if len(audio_np) < 8000:
            return ""

        segments, info = _model.transcribe(
            audio_np,
            language         = "en",    # force English — prevents Devanagari output
            beam_size        = 5,    
            initial_prompt   = _NOVA_PROMPT,   # was 5 default — slightly faster, still accurate
            vad_filter       = True,    # skip silent/non-speech regions automatically
            vad_parameters   = dict(
                min_silence_duration_ms = 400,
                speech_pad_ms           = 200,
            ),
            condition_on_previous_text = False,  # prevent hallucination loops
            temperature                = 0.0,    # deterministic
        )

        # Collect segments, filtering low-confidence ones
        parts = []
        for seg in segments:
            # avg_logprob: 0.0 = perfect, -1.0 = very uncertain
            # no_speech_prob: 1.0 = definitely silence
            if seg.avg_logprob < -0.8:
                log.debug(f"[STT] Low confidence segment skipped: '{seg.text.strip()}'")
                continue
            if seg.no_speech_prob > 0.7:
                log.debug(f"[STT] No-speech segment skipped: '{seg.text.strip()}'")
                continue
            parts.append(seg.text.strip())

        text = " ".join(parts).strip()

        # Hallucination filters
        if text.lower().rstrip(".!? ") in _HALLUCINATIONS:
            log.debug(f"[STT] Filtered hallucination: '{text}'")
            return ""

        if len(text.split()) > 20:
            log.debug(f"[STT] Rejected: too long ({len(text.split())} words)")
            return ""

        if _is_repetitive(text):
            log.debug(f"[STT] Rejected repetitive: '{text[:50]}'")
            return ""

        if text:
            log.info(f"[STT] Whisper: '{text}'")
        return text

    except Exception as e:
        log.error(f"[STT] Transcription error: {e}")
        return ""