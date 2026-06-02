# core/voice.py
import os
import time
import asyncio
import tempfile
import threading
import speech_recognition as sr
import pygame
import soundfile as sf

from config.settings import (
    NOVA_NAME, SORA_NAME,
    NOVA_VOICE_EDGE, SORA_VOICE_EDGE,
)
from core.engine import get_assistant, set_assistant
from core.lang_state import get_lang, set_lang, LANG_NAMES

# ── State ──────────────────────────────────────────────────
class VoiceState:
    IDLE      = "idle"
    LISTENING = "listening"
    THINKING  = "thinking"
    SPEAKING  = "speaking"

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
KOKORO_VOICE_NOVA_EN = "am_adam"
KOKORO_VOICE_SORA_EN = "af_heart"
KOKORO_VOICE_NOVA_HI = "hm_omega"
KOKORO_VOICE_SORA_HI = "hf_alpha"

def get_voice_ids(asst: str) -> tuple:
    is_indic = get_lang() in ("hi", "mr")
    if asst == "nova":
        return (KOKORO_VOICE_NOVA_HI if is_indic else KOKORO_VOICE_NOVA_EN), NOVA_VOICE_EDGE
    else:
        return (KOKORO_VOICE_SORA_HI if is_indic else KOKORO_VOICE_SORA_EN), SORA_VOICE_EDGE

# ── Kokoro TTS ─────────────────────────────────────────────
_kokoro_model = None
_kokoro_lock  = threading.Lock()

def _init_kokoro() -> bool:
    global _kokoro_model
    try:
        from kokoro_onnx import Kokoro
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        onnx = os.path.join(base, "kokoro-v1.0.onnx")
        bins = os.path.join(base, "voices-v1.0.bin")
        print("[TTS] Loading Kokoro...")
        _kokoro_model = Kokoro(onnx, bins)
        print("[TTS] Kokoro ready.")
        return True
    except Exception as e:
        print(f"[Kokoro Init Error] {e}")
        return False

def _clean_for_tts(text: str) -> str:
    import re
    text = re.sub(r'[\u0900-\u097F]+', '', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text.strip() else "Sorry, I could not process that."

def _speak_kokoro(text: str, voice_id: str) -> bool:
    global _kokoro_model
    with _kokoro_lock:
        if _kokoro_model is None:
            if not _init_kokoro():
                return False
        try:
            clean = _clean_for_tts(text)
            samples, sr_rate = _kokoro_model.create(
                clean, voice=voice_id, speed=1.0, lang="en-us"
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
            print(f"[Kokoro Error] {e}")
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
        print(f"[Edge TTS Error] {e}")

# ── Main speak ─────────────────────────────────────────────
pygame.mixer.init()

def speak(text: str, assistant: str = None) -> None:
    asst             = (assistant or get_assistant()).lower()
    who              = NOVA_NAME if asst == "nova" else SORA_NAME
    kokoro_v, edge_v = get_voice_ids(asst)

    print(f"[{who}] {text}")
    set_state(VoiceState.SPEAKING)
    _fire("response", {"who": asst, "text": text})

    if not _speak_kokoro(text, kokoro_v):
        _speak_edge(text, edge_v)

    set_state(VoiceState.IDLE)

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
        with sr.Microphone() as source:
            _recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
    except Exception:
        pass

# ── Mishear corrections ────────────────────────────────────
SORA_MISHEARS = ("chhora","chora","tora","tura","shora","zora","hora","swaraj","sara","sarah")
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

# ── Audio loop ─────────────────────────────────────────────
_audio_loop_running = False
_command_callback   = None

def set_command_callback(fn) -> None:
    global _command_callback
    _command_callback = fn

def audio_loop() -> None:
    global _audio_loop_running
    _audio_loop_running = True
    recognizer = sr.Recognizer()
    recognizer.energy_threshold         = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold          = 0.8

    print("[Voice] Calibrating microphone...")
    calibrate_mic()
    threading.Thread(target=_init_kokoro, daemon=True).start()

    try:
        speak_nova("N.O.V.A online. I am listening.")
        time.sleep(0.5)
        flush_mic(1.2)
    except Exception as e:
        print(f"[Startup Error] {e}")

    while _audio_loop_running:
        set_state(VoiceState.LISTENING)
        try:
            with sr.Microphone() as source:
                try:
                    audio = recognizer.listen(
                        source, timeout=None, phrase_time_limit=12)
                except sr.WaitTimeoutError:
                    continue

            set_state(VoiceState.THINKING)

            try:
                command = recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                set_state(VoiceState.LISTENING); continue
            except sr.RequestError as e:
                print(f"[STT Error] {e}")
                set_state(VoiceState.LISTENING); continue

            if not command or len(command.strip()) < 3:
                set_state(VoiceState.LISTENING); continue

            command = _correct_mishears(command.strip())
            cl      = command.lower()
            print(f"[Voice] Heard: {cl}")

            # Single word noise filter
            words = cl.split()
            known = {"nova","sora","time","date","news",
                     "weather","battery","help","stop"}
            if len(words) == 1 and words[0] not in known:
                print(f"[Voice] Noise ignored: {command}")
                set_state(VoiceState.LISTENING); continue

            _fire("transcript", {"who": "user", "text": command})

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
                set_state(VoiceState.LISTENING); continue

            # ── Assistant switch ──
            if cl.startswith("hey nova") or cl.startswith("nova ") or cl == "nova":
                set_assistant("nova")
                command = cl.replace("hey nova","").replace("nova","").strip()
                if not command:
                    speak_nova("Yes?")
                    flush_mic(0.8)
                    set_state(VoiceState.LISTENING); continue

            elif cl.startswith("hey sora") or cl.startswith("sora ") or cl == "sora":
                set_assistant("sora")
                command = cl.replace("hey sora","").replace("sora","").strip()
                if not command:
                    speak_sora("Yes?")
                    flush_mic(0.8)
                    set_state(VoiceState.LISTENING); continue

            # ── Route command ──
            if _command_callback and command:
                threading.Thread(
                    target=_command_callback,
                    args=(get_assistant(), command),
                    daemon=True
                ).start()

            flush_mic(0.5)

        except Exception as e:
            print(f"[Audio Loop Error] {e}")
            time.sleep(0.3)

def stop_audio_loop() -> None:
    global _audio_loop_running
    _audio_loop_running = False