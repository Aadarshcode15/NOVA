# core/voice.py
import os
import time
import asyncio
import tempfile
import threading
import speech_recognition as sr
import pygame
import soundfile as sf
from core.logger import log
from config.settings import MIC_DEVICE_INDEX

from config.settings import (
    NOVA_NAME, SORA_NAME,
    NOVA_VOICE_EDGE, SORA_VOICE_EDGE,
)
from core.engine import get_assistant, set_assistant
from core.lang_state import get_lang, set_lang, LANG_NAMES
from core import stt_engine
from core import perf

# ── State ──────────────────────────────────────────────────
class VoiceState:
    IDLE      = "idle"
    LISTENING = "listening"
    THINKING  = "thinking"
    SPEAKING  = "speaking"
    SLEEPING  = "sleeping"    # wake word mode — only listening for "nova"

# ── Wake word state machine ────────────────────────────────

class NovaState:
    SLEEP  = "sleep"    # only listening for wake word "nova"
    ACTIVE = "active"   # full command processing, 5-min countdown

from config.settings import ACTIVE_DURATION_SECS

_nova_state:    str   = NovaState.SLEEP
_active_until:  float = 0.0


def get_nova_state() -> str:
    return _nova_state


# REPLACE:
def _is_wake_word(text: str) -> bool:
    """
    Detects wake word in transcribed text.
    "noah" added explicitly — both Groq and local Whisper consistently
    transcribe the Indian English pronunciation of "Nova" as "Noah".
    """
    import re
    t_clean = re.sub(r"[.,!?;:\-]", " ", text.lower().strip())

    WAKE_VARIATIONS = (
        "nova", "noba", "nava", "novo", "nora",
        "noah",     # ← Groq transcribes "Nova" as "Noah" — confirmed in logs
        "no va",
        "n o v a",
    )
    for variant in WAKE_VARIATIONS:
        if variant in t_clean:
            return True
    return False


# REPLACE:
def _is_sleep_command(text: str) -> bool:
    """
    Detects sleep commands including all Groq "Nova"→"Noah" mishearings.
    Confirmed from logs:
      "Nova sleep" → "Noah Sleep" / "Noah sleep." / "Noah, sleep."
      "Nova sleep" → "No asleep." / "No sleep"
      "Nova sleep" → "Noah Leap"  (extreme mishearing)
    """
    import re
    t = re.sub(r"[.,!?;:\-]", " ", text.lower().strip())

    SLEEP_TRIGGERS = (
        # Correct transcriptions
        "nova sleep",
        "sleep nova",
        "nova go to sleep",
        "go to sleep",
        "nova stop",
        "stop listening",
        "nova rest",
        # "Noah" mishearings — Groq transcribes "Nova" as "Noah"
        "noah sleep",
        "noah go to sleep",
        "noah stop",
        "noah rest",
        # "No" mishearings — Groq transcribes "Nova sleep" as "No asleep"
        "no asleep",
        # Extreme mishearing — "Nova sleep" → "Noah Leap" (seen in logs)
        "noah leap",
    )
    return any(trigger in t for trigger in SLEEP_TRIGGERS)


def _reset_activity_timer() -> None:
    """Reset the 5-minute countdown. Call on every valid routed command."""
    global _active_until
    _active_until = time.time() + ACTIVE_DURATION_SECS


# REPLACE:
def _wake_up() -> None:
    """Transition from sleep → active. Announces wakeup, starts timer."""
    global _nova_state
    _nova_state = NovaState.ACTIVE
    _reset_activity_timer()
    set_state(VoiceState.LISTENING)
    _fire("nova_state", NovaState.ACTIVE)
    asst = get_assistant()
    speak("Neural Operative Voice Assistant online. I am ready for your command.", asst)
    log.info(f"[Wake] NOVA activated — {ACTIVE_DURATION_SECS // 60} minute window")


def _go_to_sleep(reason: str = "command") -> None:
    """Transition from active → sleep. Announces sleep, updates state."""
    global _nova_state
    _nova_state = NovaState.SLEEP
    set_state(VoiceState.SLEEPING)
    _fire("nova_state", NovaState.SLEEP)
    if reason == "timeout":
        speak("No activity detected. Going to sleep. Say Nova to wake me up.",
              get_assistant())
        log.info("[Sleep] NOVA sleeping — 5-minute timeout")
    else:
        speak("Going to sleep. Say Nova to wake me up.", get_assistant())
        log.info("[Sleep] NOVA sleeping — manual command")

_state     = VoiceState.IDLE
_callbacks = {}

def get_state() -> str: return _state

def set_state(s: str) -> None:
    global _state
    _state = s
    if "state_change" in _callbacks:
        _callbacks["state_change"](s)

def on(event: str, fn) -> None:
    _callbacks[event] = fn

def _fire(event: str, data=None) -> None:
    if event in _callbacks:
        _callbacks[event](data)

# ── Language switch triggers ───────────────────────────────
LANG_TRIGGERS = {
    "switch to hindi":    "hi",
    "speak in hindi":     "hi",
    "hindi mein baat":    "hi",
    "hindi me baat":      "hi",
    "hindi mein":         "hi",
    "bolo hindi":         "hi",
    "switch to marathi":  "mr",
    "speak in marathi":   "mr",
    "marathi mein baat":  "mr",
    "marathi mein":       "mr",
    "switch to english":  "en",
    "speak in english":   "en",
    "back to english":    "en",
    "english mein baat":  "en",
    "english mein":       "en",
}

def detect_lang_switch(command: str):
    c = command.lower().strip()
    for trigger, lang in sorted(LANG_TRIGGERS.items(), key=lambda x: len(x[0]), reverse=True):
        if trigger in c:
            return lang
    return None

# ── Kokoro voices ──────────────────────────────────────────

# Best Kokoro voices — tested for natural quality
# English: bm_george is deep, authoritative British male — best for NOVA
#          af_heart is warm, natural American female — best for SORA
# Hindi/Marathi: hm_omega (male) / hf_alpha (female) — only Indic voices available
KOKORO_VOICE_NOVA_EN = "bm_george"   # British male — calm, precise
KOKORO_VOICE_SORA_EN = "af_heart"    # American female — warm, friendly
KOKORO_VOICE_NOVA_HI = "hm_omega"    # Hindi male
KOKORO_VOICE_SORA_HI = "hf_alpha"    # Hindi female

def get_voice_ids(asst: str) -> tuple:
    lang     = get_lang()
    is_indic = lang in ("hi", "mr")

    kokoro_id = (
        (KOKORO_VOICE_NOVA_HI if asst == "nova" else KOKORO_VOICE_SORA_HI) if is_indic
        else (KOKORO_VOICE_NOVA_EN if asst == "nova" else KOKORO_VOICE_SORA_EN)
    )

    if lang == "hi":
        from config.settings import NOVA_VOICE_EDGE_HI, SORA_VOICE_EDGE_HI
        edge_id = NOVA_VOICE_EDGE_HI if asst == "nova" else SORA_VOICE_EDGE_HI
    elif lang == "mr":
        from config.settings import NOVA_VOICE_EDGE_MR, SORA_VOICE_EDGE_MR
        edge_id = NOVA_VOICE_EDGE_MR if asst == "nova" else SORA_VOICE_EDGE_MR
    else:
        edge_id = NOVA_VOICE_EDGE if asst == "nova" else SORA_VOICE_EDGE

    return kokoro_id, edge_id

# ── Kokoro TTS ─────────────────────────────────────────────
_kokoro_model = None
_kokoro_lock  = threading.Lock()

def _init_kokoro() -> bool:
    global _kokoro_model
    if _kokoro_model is not None:    # already loaded by another thread
        return True
    try:
        from kokoro_onnx import Kokoro
        from core.logger import log
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        onnx = os.path.join(base, "kokoro-v1.0.onnx")
        bins = os.path.join(base, "voices-v1.0.bin")
        log.info("[TTS] Loading Kokoro...")
        _kokoro_model = Kokoro(onnx, bins)
        log.info("[TTS] Kokoro ready.")
        return True
    except Exception as e:
        log.error(f"[Kokoro Init Error] {e}")
        return False

def _clean_for_tts(text: str) -> str:
    import re
    text = re.sub(r'[\u0900-\u097F]+', '', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text.strip() else "Sorry, I could not process that."

def _speak_kokoro(text: str, voice_id: str) -> bool:
    global _kokoro_model
    # Lock guards model init only — TTS worker is the sole caller of this function
    with _kokoro_lock:
        if _kokoro_model is None:
            if not _init_kokoro():
                return False
    # Pygame operations outside the lock — no contention since worker is sole caller
    try:
        clean = _clean_for_tts(text)
        samples, sr_rate = _kokoro_model.create(
            clean, voice=voice_id, speed=1.15, lang="en-us"
        )
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            tmp = f.name
        sf.write(tmp, samples, sr_rate)
        pygame.mixer.music.load(tmp)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()
        os.remove(tmp)
        return True
    except Exception as e:
        log.error(f"[Kokoro Error] {e}")
        return False

# ── Edge TTS fallback ──────────────────────────────────────
def _speak_edge(text: str, voice: str) -> None:
    import edge_tts
    async def _synth():
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            tmp = f.name
        await edge_tts.Communicate(text, voice).save(tmp)
        return tmp
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tmp  = loop.run_until_complete(_synth())
        pygame.mixer.music.load(tmp)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
        pygame.mixer.music.unload()
        os.remove(tmp)
    except Exception as e:
        log.error(f"[Edge TTS Error] {e}")

# ── Main speak ─────────────────────────────────────────────
# ── TTS Queue — non-blocking speak() ───────────────────────
import queue as _queue

pygame.mixer.init()

_tts_queue:          _queue.Queue      = _queue.Queue()
_tts_thread:         threading.Thread  = None
_tts_last_ended_at:  float             = 0.0   # timestamp of last completed audio chunk
_TTS_POST_BUFFER:    float             = 1.8   # seconds of silence after last chunk


def _tts_worker() -> None:
    """
    Dedicated TTS thread. Sole owner of pygame.mixer.
    Drains the queue one item at a time — no race conditions possible.
    """
    while True:
        try:
            text, asst = _tts_queue.get(timeout=1.0)
        except _queue.Empty:
            continue

        kokoro_v, edge_v = get_voice_ids(asst)
        who = NOVA_NAME if asst == "nova" else SORA_NAME
        print(f"[{who}] {text}")
        set_state(VoiceState.SPEAKING)

        is_first_audio = perf.mark_once("first_audio")

        
        try:
            if not _speak_kokoro(text, kokoro_v):
                _speak_edge(text, edge_v)
        except Exception as e:
            log.error(f"[TTS Worker Error] {e}")
        finally:
            global _tts_last_ended_at
            _tts_last_ended_at = time.time()   # ← record when this chunk finished
            set_state(VoiceState.IDLE)
            _tts_queue.task_done()

            if is_first_audio:
                perf.end_turn()


def _start_tts_worker() -> None:
    """Start the TTS worker thread once. Safe to call multiple times."""
    global _tts_thread
    if _tts_thread and _tts_thread.is_alive():
        return
    _tts_thread = threading.Thread(target=_tts_worker, daemon=True, name="TTS-Worker")
    _tts_thread.start()
    log.info("[TTS] Worker thread started.")


# Max characters to send to TTS — prevents Kokoro phoneme overflow
# (~400 chars ≈ 60 spoken words, plenty for any normal response)
_MAX_TTS_CHARS = 400

# ADD this function right before speak():

import re as _re

_SENTENCE_SPLIT = _re.compile(r'(?<=[.!?])\s+')

def _split_for_tts(text: str) -> list:
    """
    Split long responses into sentence chunks for faster perceived TTS.

    Why: Kokoro processes a 10-word sentence in ~250ms.
    A 40-word response processed as one block takes ~700ms before
    first audio. Split into sentences → first audio in ~250ms,
    rest queues behind it.

    Minimum chunk size 50 chars prevents choppy single-word clips.
    """
    if len(text) <= 90:
        return [text]              # short enough — don't split

    raw_parts = _SENTENCE_SPLIT.split(text)
    result    = []
    buffer    = ""

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        candidate = (buffer + " " + part).strip() if buffer else part
        if len(candidate) >= 50:
            result.append(candidate)
            buffer = ""
        else:
            buffer = candidate     # too short — merge with next

    if buffer:
        result.append(buffer)

    return result if result else [text]

def speak(text: str, assistant: str = None) -> None:
    """
    Non-blocking. Splits response into sentence chunks before queuing.

    Sentence chunking means Kokoro processes the first sentence (~250ms)
    and starts playing while the rest is still queuing — user hears
    first words 300-400ms sooner on multi-sentence responses.
    """
    if not text or not text.strip():
        return

    stripped = text.strip()
    asst     = (assistant or get_assistant()).lower()

    # Strip common AI preambles that slipped through the prompt rule
    for preamble in (
        "Sure! ", "Sure, ", "Of course! ", "Of course, ",
        "Certainly! ", "Certainly, ", "Great! ", "Great, ",
        "Absolutely! ", "Absolutely, ", "Happy to help! ",
    ):
        if stripped.startswith(preamble):
            stripped = stripped[len(preamble):].strip()
            break

    # Guard against code/data dumps reaching TTS
    if len(stripped) > _MAX_TTS_CHARS:
        stripped = stripped[:_MAX_TTS_CHARS].rsplit(" ", 1)[0] + "."
        log.warning(f"[TTS] Truncated long response to {_MAX_TTS_CHARS} chars")

    _fire("response", {"who": asst, "text": stripped})

    # Split into sentence chunks — each queued separately
    # First chunk starts playing ~250ms after speak() returns
    for chunk in _split_for_tts(stripped):
        if chunk.strip():
            _tts_queue.put((chunk.strip(), asst))


def speak_nova(text: str) -> None: speak(text, "nova")
def speak_sora(text: str) -> None: speak(text, "sora")

# ── STT helpers ────────────────────────────────────────────
_recognizer = sr.Recognizer()

def calibrate_mic() -> None:
    with sr.Microphone() as source:
        _recognizer.adjust_for_ambient_noise(source, duration=0.8)
    print("[Voice] Microphone calibrated.")

def flush_mic(duration: float = 0.5) -> None:
    try:
        with sr.Microphone(device_index=MIC_DEVICE_INDEX) as source:
            _recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
    except Exception:
        pass

# ── Mishear corrections ────────────────────────────────────
SORA_MISHEARS = ("chhora","chora","tora","tura","shora","zora","hora","sara","sarah")
NOVA_MISHEARS = ("innova","inova","naova","nava","noa")

def _correct_mishears(text: str) -> str:
    words = text.split()
    if not words:
        return text
    for i in range(min(2, len(words))):
        w = words[i].lower()
        if w in SORA_MISHEARS:
            words[i] = "sora"
        elif w in NOVA_MISHEARS:
            words[i] = "nova"
    return " ".join(words)

def _log_microphone_info() -> None:
    """
    Diagnostic: confirms exactly which physical microphone NOVA is
    reading from. Critical when hallucinations are 100% consistent
    across engines with zero real speech ever appearing — that
    pattern points to the wrong input device being used, not noise.
    """
    try:
        import pyaudio
        pa = pyaudio.PyAudio()
        try:
            default_info = pa.get_default_input_device_info()
            log.info(
                f"[Voice] System default input device: "
                f"'{default_info.get('name')}' (index {default_info.get('index')})"
            )
        except Exception as e:
            log.warning(f"[Voice] No default input device detected: {e}")
        pa.terminate()
    except Exception as e:
        log.warning(f"[Voice] PyAudio device query failed: {e}")

    try:
        names = sr.Microphone.list_microphone_names()
        log.info(f"[Voice] All available input devices ({len(names)} total):")
        for i, name in enumerate(names):
            log.info(f"[Voice]   [{i}] {name}")
        if MIC_DEVICE_INDEX is not None:
            log.info(f"[Voice] MIC_DEVICE_INDEX override active: using index {MIC_DEVICE_INDEX}")
        else:
            log.info("[Voice] No override set — using system default (see above)")
    except Exception as e:
        log.warning(f"[Voice] Could not enumerate input devices: {e}")

# ── Audio loop ─────────────────────────────────────────────
_audio_loop_running = False
_command_callback   = None

def set_command_callback(fn) -> None:
    global _command_callback
    _command_callback = fn

# REPLACE:
def audio_loop() -> None:
    """..."""
    global _audio_loop_running
    _audio_loop_running = True

    # REPLACE:
    _log_microphone_info()

    sleep_rec = sr.Recognizer()
    sleep_rec.energy_threshold         = 400
    sleep_rec.dynamic_energy_threshold = False
    sleep_rec.pause_threshold          = 0.5

    active_rec = sr.Recognizer()
    active_rec.energy_threshold         = 600
    active_rec.dynamic_energy_threshold = False
    active_rec.pause_threshold          = 0.8

   # REPLACE:
    # Local variable, not the module-level import — avoids the
    # global-reassignment issue entirely and self-heals if the
    # configured device index turns out to be invalid.
    active_mic_index = MIC_DEVICE_INDEX

    log.info("[Voice] Calibrating microphone...")
    try:
        with sr.Microphone(device_index=active_mic_index) as src:
            sleep_rec.adjust_for_ambient_noise(src, duration=0.8)
    except Exception as e:
        log.error(
            f"[Voice] Microphone index {active_mic_index} failed to open "
            f"({e}). Using system default microphone instead."
        )
        active_mic_index = None
        with sr.Microphone(device_index=active_mic_index) as src:
            sleep_rec.adjust_for_ambient_noise(src, duration=0.8)

    # CRITICAL: Cap sleep threshold — calibration often overshoots.
    # Sleep mode must be sensitive enough to catch a single spoken word.
    ambient = sleep_rec.energy_threshold
    sleep_rec.energy_threshold  = min(ambient, 350)
    # Active threshold needs real headroom above ambient — a narrow
    # +150 offset can sit right at the level of continuous low-grade
    # noise (fan, ANC mic self-noise, coil whine), causing listen()
    # to never detect a pause and always capture the full
    # phrase_time_limit. Wider multiplier + higher floor fixes this.
    active_rec.energy_threshold = max(min(ambient * 3, 900), 400)

    log.info(
        f"[Voice] Calibrated. Ambient: {ambient:.0f} | "
        f"Sleep threshold: {sleep_rec.energy_threshold:.0f} | "
        f"Active threshold: {active_rec.energy_threshold:.0f}"
    )

    _start_tts_worker()
    stt_engine.preload()

    # Start in ACTIVE mode — NOVA is immediately ready for 5 minutes,
    # then auto-sleeps. No need to say "Nova" right after launching.
    global _nova_state
    _nova_state = NovaState.ACTIVE
    _reset_activity_timer()
    set_state(VoiceState.LISTENING)
    _fire("nova_state", NovaState.ACTIVE)
    speak("Neural Operative Voice Assistant online. I am ready for your command.",
          get_assistant())
    log.info(f"[Voice] NOVA active on startup — {ACTIVE_DURATION_SECS // 60} minute window")

    # Notify via tray if available (non-blocking)
    def _tray_notify():
        time.sleep(3.0)
        try:
            from PyQt6.QtWidgets import QApplication
            for w in QApplication.topLevelWidgets():
                if hasattr(w, "_tray") and w._tray:
                    w._tray.notify(
                        "N.O.V.A Online",
                        f"Active for {ACTIVE_DURATION_SECS // 60} minutes. Say 'Nova' anytime after to reactivate."
                    )
                    break
        except Exception:
            pass
    threading.Thread(target=_tray_notify, daemon=True).start()

    # ── Echo guard state (active mode) ────────────────────
    _was_speaking      = False
    _speaking_ended_at = 0.0
    _ECHO_GUARD_SECS   = 1.2

    # ── Deduplication state (active mode) ─────────────────
    _last_routed_text = ""
    _last_routed_time = 0.0
    _DEDUP_WINDOW     = 6.0

    # ═══════════════════════════════════════════════════════
    # MAIN LOOP
    # ═══════════════════════════════════════════════════════
    while _audio_loop_running:

        # ───────────────────────────────────────────────────
        # SLEEP MODE
        # ───────────────────────────────────────────────────
        if _nova_state == NovaState.SLEEP:
            try:
                with sr.Microphone(device_index=active_mic_index) as src:
                    try:
                        audio = sleep_rec.listen(
                            src, timeout=None, phrase_time_limit=4
                        )
                    except sr.WaitTimeoutError:
                        continue

                # ── Try local Whisper first ──
                text = stt_engine.transcribe_wake_word(audio)

                # ── Google STT fallback if Whisper returns nothing ──
                # Whisper may not be loaded yet on first few attempts.
                # Google STT is very reliable for short single-word clips.
                if not text:
                    try:
                        text = sleep_rec.recognize_google(audio).lower()
                        log.debug(f"[Sleep] Google fallback: '{text}'")
                    except Exception:
                        pass   # silence / unrecognised — normal

                if not text:
                    continue

                # Always log what was heard in sleep mode at INFO level
                # so you can see in the console what the mic is picking up
                log.info(f"[Sleep] Heard: '{text}'")

                if _is_wake_word(text):
                    log.info("[Wake] Wake word detected!")
                    _wake_up()
                    flush_mic(1.0)

            except Exception as e:
                log.error(f"[Sleep Mode Error] {e}")
                time.sleep(0.3)
            continue

        # ───────────────────────────────────────────────────
        # ACTIVE MODE
        # ───────────────────────────────────────────────────

        # ── Auto-sleep timeout check ──
        remaining = _active_until - time.time()
        if remaining <= 0:
            _go_to_sleep(reason="timeout")
            continue

        # ── Warn at 1 minute remaining (once) ──
        if 59 <= remaining <= 61:
            log.info("[Voice] 1 minute remaining in active window")

        # REPLACE:
        # ── Echo guard — keep mic closed while TTS is active ────
        # Checks THREE conditions so sentence-split gaps don't open the mic:
        #   A) Queue has items (more chunks to play)
        #   B) State is SPEAKING (chunk currently playing)
        #   C) Last chunk ended < _TTS_POST_BUFFER seconds ago
        _now = time.time()
        tts_active = (
            not _tts_queue.empty() or
            _state == VoiceState.SPEAKING or
            (_now - _tts_last_ended_at) < _TTS_POST_BUFFER
        )

        if tts_active:
            _was_speaking = True
            time.sleep(0.08)
            continue

        if _was_speaking:
            flush_mic(0.7)
            _was_speaking = False
            log.debug("[Voice] Echo guard complete — mic open")

        set_state(VoiceState.LISTENING)

        try:
            with sr.Microphone(device_index=active_mic_index) as src:
                try:
                    audio = active_rec.listen(
                        src, timeout=None, phrase_time_limit=8
                    )
                except sr.WaitTimeoutError:
                    continue

            set_state(VoiceState.THINKING)
            perf.start_turn()

            # ── STT: Groq → local Whisper → Google ──
            command = stt_engine.transcribe(audio)
            if not command:
                try:
                    command = active_rec.recognize_google(audio)
                    log.debug("[STT] Google STT fallback used")
                except (sr.UnknownValueError, sr.RequestError):
                    set_state(VoiceState.LISTENING)
                    continue

            perf.mark("stt")

            command = _correct_mishears(command.strip())
            cl      = command.lower().strip()

            # ── Known recurring artifact filter ─────────────────
            # Catches this specific word regardless of which STT
            # engine (Groq / local / Google fallback) produced it.
            # Silent — no log line, no processing. Extend this set
            # if a new recurring false-positive word ever appears.
            _KNOWN_ARTIFACTS = {"trial", "trials"}
            if cl.rstrip(".,!?") in _KNOWN_ARTIFACTS:
                set_state(VoiceState.LISTENING)
                continue

            log.info(f"[Voice] Heard: {cl}")

            if not cl or len(cl) < 2:
                set_state(VoiceState.LISTENING)
                continue

            _fire("transcript", {"who": "user", "text": command})

            # ── Sleep command — checked FIRST, never reaches router ──
            if _is_sleep_command(cl):
                _go_to_sleep(reason="command")
                continue

            # ── Language switch ──
            new_lang = detect_lang_switch(cl)
            if new_lang is not None:
                set_lang(new_lang)
                asst = get_assistant()
                if new_lang == "hi":
                    speak("Theek hai, ab main Hindi mein baat karunga.", asst)
                elif new_lang == "mr":
                    speak("Theek aahe, aata mi Marathi madhye bolto.", asst)
                else:
                    speak("Switched back to English.", asst)
                flush_mic(0.8)
                _reset_activity_timer()
                set_state(VoiceState.LISTENING)
                continue

            # ── Assistant switch ──
            _to_nova = (
                cl.startswith("hey nova") or cl.startswith("nova ") or cl == "nova" or
                "switch to nova" in cl or "change to nova" in cl
            )
            _to_sora = (
                cl.startswith("hey sora") or cl.startswith("sora ") or cl == "sora" or
                "switch to sora" in cl or "change to sora" in cl
            )

            if _to_nova:
                set_assistant("nova")
                for p in ["hey nova", "switch to nova", "change to nova", "nova"]:
                    command = command.lower().replace(p, "").strip()
                if not command:
                    speak_nova("Yes Boss?")
                    _reset_activity_timer()
                    flush_mic(0.8)
                    set_state(VoiceState.LISTENING)
                    continue

            elif _to_sora:
                set_assistant("sora")
                for p in ["hey sora", "switch to sora", "change to sora", "sora"]:
                    command = command.lower().replace(p, "").strip()
                if not command:
                    speak_sora("Yes Boss?")
                    _reset_activity_timer()
                    flush_mic(0.8)
                    set_state(VoiceState.LISTENING)
                    continue

            # ── Single word noise filter ──
            words = cl.split()
            known = {
                "nova", "sora", "time", "date", "news",
                "weather", "battery", "help", "stop",
                "yes", "no", "ok", "okay", "sure",
                "pause", "resume", "next",
                "briefing", "calendar", "emails", "schedule",
            }
            if len(words) == 1 and words[0].rstrip(".,!?") not in known:
                log.debug(f"[Voice] Noise ignored: {command}")
                set_state(VoiceState.LISTENING)
                continue

            # ── Deduplication ──
            _now = time.time()
            if (cl == _last_routed_text and
                    _now - _last_routed_time < _DEDUP_WINDOW):
                log.debug(f"[Voice] Duplicate suppressed: '{command[:40]}'")
                set_state(VoiceState.LISTENING)
                continue
            _last_routed_text = cl
            _last_routed_time = _now

            # ── Route — reset timer on every valid command ──
            if _command_callback and command:
                _reset_activity_timer()
                log.debug(f"[Voice] Timer reset — {ACTIVE_DURATION_SECS//60}min window restarted")
                threading.Thread(
                    target=_command_callback,
                    args=(get_assistant(), command),
                    daemon=True
                ).start()

            flush_mic(0.5)

        except Exception as e:
            log.error(f"[Active Mode Error] {e}")
            time.sleep(0.3)


def stop_audio_loop() -> None:
    global _audio_loop_running
    _audio_loop_running = False