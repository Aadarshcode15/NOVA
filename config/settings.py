# config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
DATA_DIR      = BASE_DIR / "data"
MEMORY_DIR    = BASE_DIR / "memory"
REMINDER_DIR  = DATA_DIR / "reminders"
TODO_FILE     = DATA_DIR / "todos.json"
CONTACTS_FILE = BASE_DIR / "config" / "contacts.json"
MEMORY_FILE   = MEMORY_DIR / "long_term.json"

# Auto-create required directories
for d in [DATA_DIR, MEMORY_DIR, REMINDER_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API Keys ───────────────────────────────────────────────
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY", "")
WEATHER_API_KEY      = os.getenv("WEATHER_API_KEY", "")
NEWS_API_KEY         = os.getenv("NEWS_API_KEY", "")
SPOTIFY_CLIENT_ID    = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET= os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT     = "http://127.0.0.1:8888/callback"

# ── Assistant Identity ─────────────────────────────────────
NOVA_NAME        = "Nova"
SORA_NAME        = "Sora"
WAKE_NOVA        = "nova"
WAKE_SORA        = "sora"

# Gemini native voice names
NOVA_VOICE       = "Charon"    # Deep, British male
SORA_VOICE       = "Aoede"     # Warm, American female

# Edge TTS fallback voices
NOVA_VOICE_EDGE  = "en-GB-RyanNeural"
SORA_VOICE_EDGE  = "en-US-AriaNeural"

# ── AI Engine ──────────────────────────────────────────────
class Engine:
    GEMINI = "gemini"
    GROQ   = "groq"
    OLLAMA = "ollama"

GEMINI_MODEL  = "gemini-2.5-flash"
GROQ_MODEL    = "llama-3.1-8b-instant"
GROQ_VISION_MODEL  = "meta-llama/llama-4-scout-17b-16e-instruct"  # free, fast vision
OLLAMA_MODEL  = "gemma4:e4b"
OLLAMA_HOST   = "http://localhost:11434"
VISION_MODEL  = "gemini-2.5-flash"   # fallback for vision tasks if GROQ model fails

DEFAULT_ENGINE = Engine.GROQ

# ── Voice / Audio ──────────────────────────────────────────
SAMPLE_RATE       = 16000
CHANNELS          = 1
CHUNK_SIZE        = 1024
SILENCE_TIMEOUT   = 2.0       # seconds of silence before processing
MAX_RECORD_SECS   = 15        # max recording length

# ── Features ───────────────────────────────────────────────
MAX_NEWS          = 5
FACE_CHECK_INTERVAL = 8       # kept for future use

# ── UI ─────────────────────────────────────────────────────
UI_WIDTH          = 1400
UI_HEIGHT         = 860
UI_TITLE          = "N.O.V.A"
UI_SUBTITLE       = "Neural Operative Virtual Assistant"

# Colors
C_BG              = "#080d14"
C_PANEL           = "#0a1220"
C_NOVA            = "#00c8ff"    # cyan — NOVA-M
C_SORA            = "#c084fc"    # purple — SORA-F
C_GOLD            = "#f0a500"
C_GREEN           = "#00ff88"
C_ORANGE          = "#ff6b35"
C_RED             = "#ff3355"
C_DIM             = "#0d2535"
C_DIM_TXT         = "#2a4a5e"
C_TEXT            = "#a0cfe0"
C_BORDER          = "#1a3a50"

# Engine indicator colors
ENGINE_COLORS = {
    Engine.GEMINI: "#4285f4",   # Google blue
    Engine.GROQ:   "#ff6b35",   # Orange
    Engine.OLLAMA: "#00ff88",   # Green
}

# ── WhatsApp Contacts (also in contacts.json) ──────────────
DEFAULT_CONTACTS = {
    "example": "+91XXXXXXXXXX",
}
