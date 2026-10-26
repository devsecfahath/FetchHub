import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file explicitly
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file, override=True)
else:
    load_dotenv(override=True)
DOWNLOAD_DIR = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "bot.db")

# Ensure download directory exists
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Cookie support for YouTube/Instagram datacenter bypass
COOKIES_FILE_PATH = None
cookies_txt = os.getenv("COOKIES_TEXT", "").strip()
local_cookie_file = BASE_DIR / "cookies.txt"

if cookies_txt:
    try:
        local_cookie_file.write_text(cookies_txt, encoding="utf-8")
        COOKIES_FILE_PATH = str(local_cookie_file)
    except Exception:
        pass
elif local_cookie_file.exists():
    COOKIES_FILE_PATH = str(local_cookie_file)

# Bot credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs (comma-separated list of Telegram user IDs)
raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
for uid in raw_admin_ids.split(","):
    clean_uid = uid.strip()
    if clean_uid.isdigit():
        ADMIN_IDS.add(int(clean_uid))

# Limits & Settings
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))

# Telegram Bot API upload limit in MB (50MB for default cloud bots)
TELEGRAM_UPLOAD_LIMIT_MB = 50.0
# Target size for compression (buffer for safe upload)
TARGET_COMPRESSION_MB = 48.5

# Auto-cleanup settings
AUTO_DELETE_HOURS = int(os.getenv("AUTO_DELETE_HOURS", "24"))
CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "15"))

# Supported platform display names
PLATFORM_EMOJIS = {
    "youtube": "🔴 YouTube",
    "instagram": "📸 Instagram",
    "tiktok": "🎵 TikTok",
    "facebook": "🔵 Facebook",
    "twitter": "🐦 X (Twitter)",
    "generic": "🌐 Web Media"
}
