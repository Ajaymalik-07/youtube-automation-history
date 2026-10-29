import os
import json

# ─────────────────────────────────────────────────────────────────────────────
#  YAAS — youtube-agentic-ai-studio · Configuration
#  API keys live in .env (git-ignored) — copy .env.example to .env, or paste
#  them into the GUI's Settings page, which writes .env for you.
#  All settings are documented. Change only what you need.
# ─────────────────────────────────────────────────────────────────────────────

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _load_env(path: str = ENV_PATH) -> None:
    """Minimal .env reader (no extra dependency). Real env vars win."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def save_env(values: dict, path: str = ENV_PATH) -> None:
    """Update KEY=value pairs in .env, keeping comments and unrelated keys."""
    for k, v in values.items():
        os.environ[str(k)] = str(v)
    lines = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    remaining = dict(values)
    for i, line in enumerate(lines):
        k = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and k in remaining:
            lines[i] = f"{k}={remaining.pop(k)}"
    lines += [f"{k}={v}" for k, v in remaining.items()]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    # Also sync client_secret.json if YouTube credentials changed
    sync_client_secret_file()


def sync_client_secret_file() -> None:
    """Sync between .env (YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET) and client_secret.json."""
    cs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client_secret.json")
    cid = os.getenv("YOUTUBE_CLIENT_ID", "").strip()
    csec = os.getenv("YOUTUBE_CLIENT_SECRET", "").strip()

    if cid and csec and not cid.startswith("YOUR_"):
        data = {
            "installed": {
                "client_id": cid,
                "project_id": "youtube-agentic-studio",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": csec,
                "redirect_uris": ["http://localhost", "http://localhost:8080"]
            }
        }
        try:
            with open(cs_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
    elif os.path.exists(cs_path):
        try:
            with open(cs_path, encoding="utf-8") as f:
                data = json.load(f)
            inst = data.get("installed") or data.get("web") or {}
            file_cid = inst.get("client_id", "")
            file_csec = inst.get("client_secret", "")
            if file_cid and "YOUR_CLIENT_ID" not in file_cid:
                os.environ.setdefault("YOUTUBE_CLIENT_ID", file_cid)
                if file_csec and "YOUR_CLIENT_SECRET" not in file_csec:
                    os.environ.setdefault("YOUTUBE_CLIENT_SECRET", file_csec)
        except Exception:
            pass


_load_env()
sync_client_secret_file()

# ─────────────────────────────────────────
#  API Keys  (all free-tier — only Gemini is recommended; the rest are optional)
# ─────────────────────────────────────────
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY",     "")   # aistudio.google.com/apikey
PEXELS_API_KEY     = os.getenv("PEXELS_API_KEY",     "")   # pexels.com/api
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")   # optional, unused by default

# Optional free keys — each one unlocks an extra provider
PIXABAY_API_KEY    = os.getenv("PIXABAY_API_KEY",    "")   # pixabay.com/api/docs — more stock images
GROQ_API_KEY       = os.getenv("GROQ_API_KEY",       "")   # console.groq.com — fast LLM fallback
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")   # openrouter.ai — free LLM fallback
YOUTUBE_API_KEY    = os.getenv("YOUTUBE_API_KEY",    "")   # console.cloud.google.com — channel stats
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")   # UC… id or @handle

# YouTube OAuth Upload & Direct Publishing (console.cloud.google.com/apis/credentials)
YOUTUBE_CLIENT_ID           = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET       = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_OAUTH_CLIENT_ID     = YOUTUBE_CLIENT_ID
YOUTUBE_OAUTH_CLIENT_SECRET = YOUTUBE_CLIENT_SECRET

# Email Notification on Upload & Analytics Dispatch
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "ajaymobulous@gmail.com")
SMTP_HOST          = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT          = int(os.getenv("SMTP_PORT", 587))
SMTP_USER          = os.getenv("SMTP_USER", "") or os.getenv("NOTIFICATION_EMAIL", "ajaymobulous@gmail.com")
SMTP_PASSWORD      = os.getenv("SMTP_PASSWORD", "")

# Settings the GUI stores in .env rather than in this file
ENV_KEYS = [
    "GEMINI_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY", "GROQ_API_KEY",
    "OPENROUTER_API_KEY", "YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID",
    "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET",
    "NOTIFICATION_EMAIL", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
]

# ─────────────────────────────────────────
#  Free API stack  (keyless — work out of the box)
# ─────────────────────────────────────────
# Ground every script in real facts from Wikipedia + arXiv, and cite them
FACT_GROUNDING = True

# When Gemini has no key or runs out of quota: Groq → OpenRouter → Pollinations
# (Pollinations is keyless, so the pipeline never dead-ends)
KEYLESS_LLM_FALLBACK = True
GROQ_MODEL           = "llama-3.3-70b-versatile"
OPENROUTER_MODEL     = "meta-llama/llama-3.3-70b-instruct:free"

# Image sources tried after Pexels, in order:
#   pixabay (key) · nasa (public domain, space topics) · openverse (CC) · pollinations (AI)
IMAGE_SOURCES = ["pixabay", "nasa", "openverse", "pollinations"]

import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

# Trend Radar — Google Trends region and arXiv fields to watch
TRENDS_GEO       = "IN"
ARXIV_CATEGORIES = ["astro-ph.CO", "gr-qc", "quant-ph", "cs.AI", "q-bio.NC"]

# ─────────────────────────────────────────
#  Your Channel Identity — History & Ancient Civilizations
#  The more specific you are, the better the AI's topic suggestions.
# ─────────────────────────────────────────
CHANNEL_DESCRIPTION = """
A cinematic and deeply researched History documentary channel exploring the greatest mysteries of ancient civilizations, lost empires, legendary rulers, shocking archaeological discoveries, and pivotal historical battles that shaped humanity.
Every video is an immersive 15+ minute deep-dive combining dramatic storytelling, verified historical records, rare insights, and intriguing what-if historical paradoxes.
Tone: cinematic, gripping, authoritative, and awe-inspiring, catering to history enthusiasts in India and worldwide.
"""
CHANNEL_NAME = "History Chronicles | इतिहास के रहस्य"   # shown on-screen and in upload metadata

# On-video branding: the "▶ CHANNEL NAME" tag in the hook and on Shorts,
# plus the channel line on thumbnails. Leave BRAND_TEXT empty to use CHANNEL_NAME.
SHOW_CHANNEL_BRAND = True
BRAND_TEXT         = ""

# Default thumbnail style: "impact" | "cinematic" | "split" | "studio"
# (you can switch per video on the Review page)
THUMB_STYLE        = "cinematic"

# Optional video watermark: text burnt into the corner of every video. Leave empty for no watermark.
VIDEO_WATERMARK    = ""

# Adds attribution to descriptions
CREDIT_YAAS        = False


def brand_text() -> str:
    """The on-video brand label, or "" when branding is switched off."""
    if not SHOW_CHANNEL_BRAND:
        return ""
    return (BRAND_TEXT or CHANNEL_NAME or "").strip()

# ─────────────────────────────────────────
#  Language & Voice (Edge TTS — free, no API key)
#  Default language: Hindi ("hi")
#  Hindi Primary Voice: hi-IN-MadhurNeural (deep, dramatic male voice)
#  English Secondary Voice: en-US-AndrewNeural (warm, authoritative)
# ─────────────────────────────────────────
DEFAULT_LANGUAGE = "hi"
VOICE_ID         = "hi-IN-MadhurNeural"
VOICE_ID_EN      = "en-US-AndrewNeural"
VOICE_RATE       = "-4%"     # slightly measured pace for historical gravity
VOICE_PITCH      = "-2Hz"    # resonant documentary tone
VIDEO_MIN_MINUTES = 10   # target duration for long videos (safe under YouTube's 15-min cap)
VIDEO_MAX_MINUTES = 14   # maximum duration cap (10–14 minutes)

# ─────────────────────────────────────────
#  AI Model
#  Starting model for the fallback chain — the system auto-switches
#  through all models below if quota or errors are hit.
#  Options (free tier):
#    gemini-3.5-flash        — recommended high quality (fast, high capacity) ← default
#    gemini-3.5-flash-lite   — fastest lightweight
#    gemini-3.1-flash-lite   — high reliability
#    gemini-3-flash-preview  — high capacity
#    gemini-3.8-flash        — latest flagship
#    gemma-4-31b-it          — Gemma 4 31B dense reasoning
# ─────────────────────────────────────────
GEMINI_MODEL = "gemini-3.5-flash"

# ─────────────────────────────────────────
# ─────────────────────────────────────────
#  Video Dimensions & Resolution (1080p, 2K, 4K)
#  "1080p" : 1920×1080 (Full HD)
#  "2k"    : 2560×1440 (1440p QHD — Sweet Spot: Forces YouTube to use the premium VP09 codec)
#  "4k"    : 3840×2160 (4K UHD — official 4K badge on YouTube)
# ─────────────────────────────────────────
VIDEO_RESOLUTION = "2k"   # "1080p" | "2k" | "4k"

RESOLUTIONS = {
    "1080p": (1920, 1080),
    "2k":    (2560, 1440),
    "4k":    (3840, 2160),
}

VIDEO_WIDTH, VIDEO_HEIGHT = RESOLUTIONS.get(VIDEO_RESOLUTION, (2560, 1440))
VIDEO_FPS    = 24

# YouTube Shorts dimensions (9:16 vertical)
SHORTS_WIDTH  = 1080
SHORTS_HEIGHT = 1920
SHORTS_FPS    = 30

# ─── Visual Style ───────────────────────
# Ken Burns effect: how much to zoom/pan each image
KB_ZOOM_START = 1.00    # starting scale (1.0 = no zoom)
KB_ZOOM_END   = 1.10    # ending scale   (1.1 = 10% zoom in)

# Image crossfade duration (seconds)
# 0.0 = instant cut  |  0.5 = snappy  |  0.7 = smooth  |  1.2 = dreamy
CROSSFADE_DURATION = 0.7

# Normal video B-roll cycling
BROLL_INTERVAL  = 10.0   # seconds each image stays on screen
BROLL_XFADE_DUR =  1.2   # crossfade duration (must be < BROLL_INTERVAL)

# Render quality preset (ffmpeg libx264)
# "ultrafast" = fastest/largest  |  "veryfast" = balanced  |  "medium" = best quality
RENDER_PRESET = "ultrafast"

# Overlay opacity: lower = more image visible but text harder to read (0–1)
OVERLAY_OPACITY = 0.62

# Colour palette — customise to match your brand
COLORS = {
    "background": (10,  10,  20),
    "overlay":    (0,   0,   0),
    "primary":    (99,  102, 241),   # indigo
    "accent":     (167, 139, 250),   # purple
    "highlight":  (251, 191,  36),   # amber
    "white":      (255, 255, 255),
    "light":      (199, 210, 254),   # indigo-200
    "success":    (52,  211, 153),
    "red":        (239,  68,  68),
}

# Fonts — add your own .ttf paths for best results; system falls back gracefully
FONT_PATHS = {
    "bold":    [
        "C:/Windows/Fonts/Nirmala.ttc",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Bold.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
    "regular": [
        "C:/Windows/Fonts/Nirmala.ttc",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "light":   [
        "C:/Windows/Fonts/segoeuil.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Light.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
}

# ─────────────────────────────────────────
#  Review Server
# ─────────────────────────────────────────
REVIEW_PORT = 5050

# ─────────────────────────────────────────
#  YouTube Upload
# ─────────────────────────────────────────
YOUTUBE_CLIENT_SECRET_FILE = "client_secret.json"   # OAuth credentials file path
YOUTUBE_CLIENT_SECRET      = os.getenv("YOUTUBE_CLIENT_SECRET", "")  # Client Secret string
YOUTUBE_SCOPES             = ["https://www.googleapis.com/auth/youtube.upload"]
VIDEO_CATEGORY_ID          = "27"       # 27 = Education
VIDEO_PRIVACY              = "public"   # "public" | "unlisted" | "private"

# ─────────────────────────────────────────
#  Background Music
#  Drop MP3/WAV files into the  music library/  folder.
#  Tracks are shuffled and looped automatically to match video length.
# ─────────────────────────────────────────
MUSIC_ENABLED     = True
MUSIC_VOLUME      = 0.12          # 0.0–1.0  (0.12 = subtle underscore)
MUSIC_LIBRARY_DIR = os.path.join(os.path.dirname(__file__), "music library")

# ─────────────────────────────────────────
#  Paths  (do not change unless you know what you're doing)
# ─────────────────────────────────────────
OUTPUT_DIR   = "output"
IMAGES_DIR   = "output/images"

# ─────────────────────────────────────────
#  Weekly Editorial Content Plan (Long-Form & Shorts)
# ─────────────────────────────────────────
WEEKLY_THEMES = {
    "Monday": {
        "theme": "Rivers & Ancient Civilizations",
        "theme_hi": "नदियां और प्राचीन सभ्यताएं",
        "description": "Exploration of civilization cradles, ancient water engineering, and riverside empires (Indus Valley, Nile, Mesopotamia, Yellow River, Ganga, Amazon).",
        "keywords": ["Indus Valley", "Ancient Rivers", "Mesopotamia", "Nile Civilization", "Saraswati River", "Vedic Civilization"],
        "sample_topics": [
            "Indus Valley & The Lost Saraswati River: How a River's Death Ended a Civilization",
            "The Sacred Ganga: 5,000 Years of Hidden Archaeological Secrets",
            "The Nile River & The Pharaohs' Divine Waterways",
            "Mesopotamian Irrigation: The World's First Engineered Cities",
            "Lost Amazonian River Civilizations Unveiled by LIDAR",
        ],
    },
    "Tuesday": {
        "theme": "Ghosts & Haunted Places",
        "theme_hi": "भूतिया और शापित ऐतिहासिक स्थान",
        "description": "Dark history, legendary haunted forts, cursed monuments, and paranormal mysteries grounded in real historical tragedies.",
        "keywords": ["Bhangarh Fort", "Kuldhara", "Haunted History", "Cursed Forts", "Dark Heritage", "Ghost Legends"],
        "sample_topics": [
            "Bhangarh Fort: The 400-Year-Old Curse Where Nobody Enters After Dark",
            "The Abandoned Village of Kuldhara: 84 Villages Vanished in One Night",
            "Shaniwar Wada: The Tragic Peshwa Betrayal & The Midnight Screams",
            "The Tower of London: 1,000 Years of Royal Executions and Specters",
            "Poveglia Island: The Plague Colony Locked Away in Venice",
        ],
    },
    "Wednesday": {
        "theme": "Kings, Queens & Empires",
        "theme_hi": "राजा, रानियां और महान साम्राज्य",
        "description": "Biographies, royal power struggles, military conquests, court intrigue, and the rise & fall of empires (Mauryas, Guptas, Cholas, Mughals, Marathas, etc.).",
        "keywords": ["Ancient Empires", "Chandragupta Maurya", "Chola Dynasty", "Mughal Empire", "Gupta Empire", "Chhatrapati Shivaji"],
        "sample_topics": [
            "Samudragupta: The Undefeated Conqueror of Ancient India",
            "Rajaraja Chola I: The Naval Mastermind Who Conquered Southeast Asia",
            "Chanakya & Chandragupta: The Mastermind Behind the Maurya Empire",
            "Rani Durgavati: The Gondwana Queen Who Defied the Mughal Might",
            "Chhatrapati Shivaji Maharaj: Guerrilla Warfare That Shattered Empires",
        ],
    },
    "Thursday": {
        "theme": "Ancient Mysteries",
        "theme_hi": "प्राचीन रहस्य और अनसुलझी पहेलियां",
        "description": "Unexplained ancient technologies, undeciphered scripts, baffling monoliths, and ancient scientific wonders.",
        "keywords": ["Kailash Temple", "Iron Pillar", "Ancient Mysteries", "Lost Technology", "Archaeology Secrets", "Monoliths"],
        "sample_topics": [
            "Kailash Temple Ellora: How 200,000 Tons of Rock Were Carved From Top-Down",
            "The 1,600-Year Rustless Iron Pillar of Delhi: The Metallurgical Mystery Solved",
            "The Undeciphered Indus Script: 4,000-Year-Old Enigma",
            "The Antikythera Mechanism: A 2,000-Year-Old Astronomical Computer",
            "The Secret Chambers & Geometric Codes of the Great Pyramid",
        ],
    },
    "Friday": {
        "theme": "Wars & Battles",
        "theme_hi": "ऐतिहासिक युद्ध और महासंग्राम",
        "description": "Pivotal military clashes, strategic masterstrokes, revolutionary battlefield tactics, and conflicts that reshaped civilizations.",
        "keywords": ["Battle of Haldighati", "Panipat", "Tarain", "Kalinga War", "Ancient Warfare", "Epic Battles"],
        "sample_topics": [
            "The Battle of Haldighati: Maharana Pratap's Immortal Stand",
            "The Kalinga War 261 BC: The Carnage That Transformed Emperor Ashoka",
            "The First Battle of Panipat 1526: Gunpowder vs 100,000 Troops",
            "The Battle of Tarain 1192: The Turning Point of Indian History",
            "The Battle of Plassey 1757: How 3,000 Men Won an Empire",
        ],
    },
    "Saturday": {
        "theme": "Lost Cities & Forgotten Places",
        "theme_hi": "खोए हुए शहर और भूले-बिसरे स्थान",
        "description": "Cities submerged beneath waves, buried in sands, or hidden deep within jungles (Dwarka, Rakhigarhi, Mohenjo-Daro, Petra, Pompeii).",
        "keywords": ["Dwarka", "Lost Cities", "Rakhigarhi", "Mohenjo-Daro", "Petra", "Sunken Civilizations"],
        "sample_topics": [
            "The Submerged City of Dwarka: Marine Archaeology Meets Sacred Text",
            "Rakhigarhi: The Forgotten Mega-City Larger Than Mohenjo-Daro",
            "Mohenjo-Daro: The 4,500-Year-Old City With Planned Streets & Sanitation",
            "Petra: The Rose-Red City Carved Inside Desert Canyons",
            "Heracleion: The Sunken Egyptian Metropolis Rediscovered Under the Sea",
        ],
    },
    "Sunday": {
        "theme": "Historical Stories & Legends",
        "theme_hi": "ऐतिहासिक कहानियां और अमर गाथाएं",
        "description": "Epic sagas, legendary travelers, archaeological reality behind myths, and cultural chronicles that lived for thousands of years.",
        "keywords": ["Historical Legends", "Ram Setu", "Koh-i-Noor", "Nalanda", "Ancient Chronicles", "Historical Myths"],
        "sample_topics": [
            "Ram Setu / Adam's Bridge: Geological and Historical Reality",
            "The Koh-i-Noor Diamond: A 700-Year Chronicle of Curses and Conquests",
            "Xuanzang at Nalanda: What a Chinese Scholar Recorded in Ancient India",
            "The Legend of Rani Padmini and the Siege of Chittorgarh",
            "Megasthenes' Indica: An Ancient Greek's Account of Chandragupta's India",
        ],
    },
}


def get_weekly_theme(day_or_dt=None) -> dict:
    """
    Returns the theme details for a given day name (e.g., 'Monday') or datetime.
    Defaults to current day in India Standard Time (IST).
    """
    from datetime import datetime, timezone, timedelta
    if day_or_dt is None:
        ist = timezone(timedelta(hours=5, minutes=30))
        day_or_dt = datetime.now(timezone.utc).astimezone(ist).strftime("%A")
    elif hasattr(day_or_dt, "strftime"):
        day_or_dt = day_or_dt.strftime("%A")
    elif isinstance(day_or_dt, str) and "-" in day_or_dt:
        # e.g. "2026-10-29"
        try:
            day_or_dt = datetime.strptime(day_or_dt, "%Y-%m-%d").strftime("%A")
        except Exception:
            day_or_dt = "Monday"
    day_name = str(day_or_dt).capitalize()
    info = WEEKLY_THEMES.get(day_name, WEEKLY_THEMES["Monday"])
    return {"day": day_name, **info}

