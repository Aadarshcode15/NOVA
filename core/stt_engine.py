# core/stt_engine.py
import threading
import numpy as np
import speech_recognition as sr
from core.logger import log

# ── Model config ────────────────────────────────────────────
_MODEL_SIZE   = "small.en"    # local offline fallback + wake word detection
_COMPUTE_TYPE = "int8"
_DEVICE       = "cpu"

_model      = None
_model_lock = threading.Lock()


# ── Model loading ───────────────────────────────────────────

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
            log.info(f"[STT] Whisper ready ({_MODEL_SIZE}).")
            return True
        except Exception as e:
            log.error(f"[STT] Failed to load Whisper: {e}")
            return False


def preload() -> None:
    """Pre-load model in background so first command isn't delayed."""
    threading.Thread(target=load_model, daemon=True, name="Whisper-Loader").start()


def is_ready() -> bool:
    return _model is not None


# ── Audio conversion ─────────────────────────────────────────

def _to_numpy(audio: sr.AudioData) -> np.ndarray:
    """Convert sr.AudioData → float32 numpy array at 16 kHz."""
    wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
    samples   = np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32)
    return samples / 32768.0

# ── Energy gate ───────────────────────────────────────────────
# Root cause of repeated hallucinations ("trial", etc.): continuous
# low-level ambient noise (fan cycling, ANC mic self-noise, coil
# whine) sits just above energy_threshold, so sr.listen() never
# detects a real pause and always records the full phrase_time_limit.
# Whisper then hallucinates the same word from that noise floor.
#
# This gate checks actual audio LOUDNESS (RMS) regardless of what
# word gets transcribed — real speech is meaningfully louder than
# background hum, even when the hum crosses the (low) energy_threshold.

_MIN_RMS_ENERGY = 0.012   # tune via logged values if hallucinations persist

def _rms_energy(samples: np.ndarray) -> float:
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))

# ── NOVA vocabulary prompt ───────────────────────────────────
# Groq hard limit: 896 characters. Keep this short — a vocabulary
# hint, not a manual. Also used as initial_prompt for LOCAL Whisper
# only (never passed to Groq — see _transcribe_groq for why).

CONTACT_NAMES = "Raj, Priya, Amit, Rohan, Ananya"

_NOVA_PROMPT = (
    f"NOVA voice assistant. Mumbai, India. Contacts: {CONTACT_NAMES}. "
    "Commands: open Chrome, Spotify, WhatsApp, VS Code, Discord, YouTube, "
    "volume up, volume down, set volume to fifty, brightness, screenshot, "
    "what is the weather, what time is it, check battery, "
    "play music, pause music, next song, previous song, "
    "morning briefing, daily briefing, give me my briefing, "
    "check my emails, read my emails, send email, "
    "what's on my calendar, add to my calendar, create an event, "
    "write code, run code, explain code, create HTML page, build website, "
    "remind me to, add to my to-do list, "
    "search Amazon for, search LinkedIn for, browse to, "
    "see the clipboard, what did I copy, smart clipboard, "
    "record morning routine, run morning routine, stop recording, list routines, "
    "add a voice note, read my journal, "
    "switch to Gemini, switch to Groq, switch to Ollama, "
    "remember that, what do you know about me, performance stats."
)


# ── Hallucination filters ────────────────────────────────────

_HALLUCINATIONS = frozenset({
    "", ".", "..", "...", "you", "thank you", "thanks",
    "thank you.", "thanks.", "bye", "bye.", "okay", "ok",
    "thank you for watching.", "thanks for watching.",
    "please subscribe.", "like and subscribe.",
    "mumbai, india.", "mumbai, india", "contacts.", "contacts",
    "mailand, the", "mardi, india.", "mardi, india",
    "and the", "and the.", "i'm going to go.", "i'm going to go",
    "be your name", "maddin", "mailand","trial", "trial.", "trials",
})

# Known artifacts from truly silent/near-silent audio in sleep mode —
# confirmed via testing with headphones (no ambient noise at all):
# greedy/low-beam decoding on silence reliably collapses onto the
# same arbitrary token every time. This is an algorithmic quirk of
# Whisper on near-zero-signal input, not real transcription.
_SILENCE_ARTIFACTS = frozenset({
    "trial", "trials", "you", "thank you", "bye", "",
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


# ── Groq hosted Whisper (primary, online) ────────────────────

def _transcribe_groq(audio: sr.AudioData) -> str:
    """
    Transcribe using Groq's hosted whisper-large-v3-turbo.

    NO initial_prompt — passing _NOVA_PROMPT here previously caused
    Groq to hallucinate prompt vocabulary as fake commands on silent/
    noisy audio (confirmed root cause from earlier session logs).
    Local faster-whisper is safe with the prompt because we apply
    segment-level confidence filtering after the fact; Groq's plain-
    string response format gives us nothing to filter against.
    """
    import os
    import tempfile
    from groq import Groq
    from config.settings import GROQ_API_KEY

    if not GROQ_API_KEY:
        return ""

    wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
    if len(wav_bytes) < 25600:   # < 0.8s — likely echo/noise, not speech
        return ""

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp_path = f.name

        client = Groq(api_key=GROQ_API_KEY)
        with open(tmp_path, "rb") as f:
            response = client.audio.transcriptions.create(
                file            = ("audio.wav", f.read()),
                model           = "whisper-large-v3-turbo",
                language        = "en",
                response_format = "text",
            )

        text = (response if isinstance(response, str) else
                getattr(response, "text", "")).strip()

        if not text:
            return ""

        normalised = text.lower().rstrip(".!? ")
        if normalised in _HALLUCINATIONS:
            log.debug(f"[STT] Groq: filtered hallucination '{text[:40]}'")
            return ""

        words = text.split()
        if len(words) < 2:
            log.debug(f"[STT] Groq: too short ({len(words)} words) '{text}'")
            return ""
        if len(words) > 20:
            log.debug(f"[STT] Groq: too long ({len(words)} words), likely noise")
            return ""

        from collections import Counter
        word_counts       = Counter(w.lower().strip(".,!?") for w in words)
        top_word, top_ct  = word_counts.most_common(1)[0]
        if top_ct / len(words) > 0.35 and len(words) >= 4:
            log.debug(f"[STT] Groq: repetition loop detected '{text[:50]}'")
            return ""

        if _is_repetitive(text):
            log.debug(f"[STT] Groq: repetitive pattern detected")
            return ""

        log.debug(f"[STT] Groq Whisper: '{text}'")
        return text

    except Exception as e:
        err = str(e)
        if "400" in err or "invalid_request" in err.lower():
            log.debug(f"[STT] Groq 400 (bad audio): {err[:80]}")
        elif "429" in err or "rate_limit" in err.lower():
            import re
            wait_match = re.search(r"Please try again in ([\d.]+)s", err)
            wait = float(wait_match.group(1)) if wait_match else 30.0
            log.warning(f"[STT] Groq rate limited — retry in {wait:.0f}s")
        elif "401" in err or "authentication" in err.lower():
            log.error("[STT] Groq API key invalid — check GROQ_API_KEY in .env")
        elif "503" in err or "502" in err or "unavailable" in err.lower():
            log.debug(f"[STT] Groq server unavailable — using local Whisper")
        else:
            log.debug(f"[STT] Groq unavailable: {err[:80]}")
        return ""

    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass


# ── Main command transcription (active mode) ─────────────────

def transcribe(audio: sr.AudioData) -> str:
    """
    Full command transcription: Groq (fast, accurate) → local Whisper
    (offline fallback). Used only in ACTIVE mode.
    """
    global _model

    # ── Energy gate — reject before wasting an API call ──
    rms = _rms_energy(_to_numpy(audio))
    if rms < _MIN_RMS_ENERGY:
        log.debug(f"[STT] Rejected: audio too quiet (RMS {rms:.4f} < {_MIN_RMS_ENERGY})")
        return ""

    text = _transcribe_groq(audio)
    if text:
        log.info(f"[STT] Groq ✓ '{text}'")
        return text

    log.debug("[STT] Groq unavailable — using local Whisper")

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


# ── Wake word transcription (sleep mode) ──────────────────────

def transcribe_wake_word(audio: sr.AudioData) -> str:
    """
    Fast local-only transcription used ONLY in sleep mode.
    Local Whisper only — zero API cost while sleeping.

    beam_size=3 (not 1): greedy decoding (beam_size=1) on truly
    silent audio reliably hallucinates the SAME word every call
    (observed: 'trial' repeating every ~5s with headphones on and
    zero ambient noise). Wider beam search + no_speech_threshold
    correctly identifies silence instead of guessing a token.
    """
    global _model

    if _model is None:
        if not load_model():
            return ""

    try:
        wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
        if len(wav_bytes) < 8000:
            return ""

        audio_np = _to_numpy(audio)

        # ── Energy gate — same protection as active-mode transcribe() ──
        rms = _rms_energy(audio_np)
        if rms < _MIN_RMS_ENERGY:
            log.debug(f"[STT] Wake: rejected — audio too quiet (RMS {rms:.4f})")
            return ""

        with _model_lock:
            segments, info = _model.transcribe(
                audio_np,
                language                   = "en",
                beam_size                  = 3,
                vad_filter                 = True,
                vad_parameters             = dict(
                    min_silence_duration_ms = 300,
                    speech_pad_ms           = 100,
                ),
                condition_on_previous_text = False,
                temperature                = 0.0,
                no_speech_threshold        = 0.6,
            )

        parts = []
        for seg in segments:
            if seg.no_speech_prob > 0.5:
                continue
            parts.append(seg.text.strip())

        text = " ".join(parts).strip().lower()

        if text in _SILENCE_ARTIFACTS:
            return ""

        if text:
            log.info(f"[STT] Wake Whisper: '{text}'")
        return text

    except Exception as e:
        log.debug(f"[STT] Wake word transcription error: {e}")
        return ""