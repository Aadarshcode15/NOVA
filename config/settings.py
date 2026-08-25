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

# ── Microphone device override ──────────────────────────────
# Leave blank to use system default. If diagnostics show NOVA is
# listening to the wrong device, set this to the correct index
# (shown in the startup log under "Available input devices").
MIC_DEVICE_INDEX = os.getenv("MIC_DEVICE_INDEX", "").strip()
MIC_DEVICE_INDEX = int(MIC_DEVICE_INDEX) if MIC_DEVICE_INDEX.isdigit() else None

# ── Assistant Identity ─────────────────────────────────────
NOVA_NAME        = "Nova"
SORA_NAME        = "Sora"
WAKE_NOVA        = "nova"
WAKE_SORA        = "sora"

# Edge TTS fallback voices — English
NOVA_VOICE_EDGE     = "en-GB-RyanNeural"
SORA_VOICE_EDGE     = "en-US-AriaNeural"
# Edge TTS fallback voices — Hindi / Marathi (third-tier fallback only)
NOVA_VOICE_EDGE_HI  = "hi-IN-MadhurNeural"
SORA_VOICE_EDGE_HI  = "hi-IN-SwaraNeural"
NOVA_VOICE_EDGE_MR  = "mr-IN-ManoharNeural"
SORA_VOICE_EDGE_MR  = "mr-IN-AarohiNeural"

# ── AI Engine ──────────────────────────────────────────────
class Engine:
    GEMINI = "gemini"
    GROQ   = "groq"
    OLLAMA = "ollama"

# REPLACE:
GEMINI_MODEL  = "gemini-2.5-flash"      # AI reasoning only — TTS removed
GROQ_MODEL    = "openai/gpt-oss-20b"
GROQ_VISION_MODEL  = "qwen/qwen3.6-27b"  # free, fast vision
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
MAX_NEWS              = 5
FACE_CHECK_INTERVAL   = 8
MORNING_BRIEFING_TIME = os.getenv("MORNING_BRIEFING_TIME", "08:00")
ACTIVE_DURATION_SECS  = int(os.getenv("NOVA_ACTIVE_SECS", "300"))  # 5 minutes default 

# ── UI ─────────────────────────────────────────────────────
UI_WIDTH          = 1400
UI_HEIGHT         = 860
UI_TITLE          = "N.O.V.A"
UI_SUBTITLE       = "Neural Operative Virtual Assistant"

# Colors — Professional Tech Dashboard Theme
C_BG              = "#04070d"
C_PANEL           = "#070c16"
C_NOVA            = "#00d4ff"    # cyan — NOVA-M
C_SORA            = "#c084fc"    # purple — SORA-F
C_GOLD            = "#fbbf24"
C_GREEN           = "#22c55e"
C_ORANGE          = "#fb923c"
C_RED             = "#f43f5e"
C_DIM             = "#0d1f2e"
C_DIM_TXT         = "#3c5a70"
C_TEXT            = "#c5dce8"
C_BORDER          = "#16334a"

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
