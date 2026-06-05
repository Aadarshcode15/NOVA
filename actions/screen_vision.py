# actions/screen_vision.py
import os
import base64
import tempfile
import pyautogui
from core.voice import speak
from core.engine import query_vision
from core.logger import log

TRIGGERS = (
    "what's on my screen", "describe my screen", "what do you see",
    "look at my screen", "read my screen", "analyse my screen",
    "analyze my screen", "what is on screen", "screen description",
    "what's on screen"
)

def handle_vision(command: str) -> bool:
    c = command.lower()
    if not any(t in c for t in TRIGGERS):
        return False

    speak("Let me take a look.")
    try:
        screenshot = pyautogui.screenshot()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            tmp_path = f.name
        screenshot.save(tmp_path)
        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
        os.remove(tmp_path)

        prompt = (
            "You are NOVA, a voice assistant. "
            "Describe what is on this screen in 2 to 3 short spoken sentences. "
            "Be concise — this will be spoken aloud. "
            "No markdown, no bullet points."
        )
        description = query_vision(img_b64, prompt)
        speak(description)
    except Exception as e:
        log.error(f"[Vision Error] {e}")
        speak("Sorry, I couldn't analyse the screen right now.")
    return True