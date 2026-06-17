import os
import pytz

# ===================== TELEGRAM CONFIG =====================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ===================== DATABASE CONFIG =====================
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "nofap_streak_bot")

# ===================== ADMIN CONFIG =====================
# Comma separated list of admin user ids, e.g. "12345,67890"
ADMIN_IDS = [
    int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# ===================== TIMEZONE CONFIG =====================
IST = pytz.timezone("Asia/Kolkata")

# ===================== STREAK WINDOW CONFIG =====================
# Broadcast goes out at 5:00 AM IST every day, asking about the PREVIOUS day's streak.
BROADCAST_HOUR_IST = 5
BROADCAST_MINUTE_IST = 0

# Entry window: 5:00 AM IST to 11:59 PM IST (same day as broadcast)
ENTRY_START_HOUR_IST = 5
ENTRY_START_MINUTE_IST = 0
ENTRY_END_HOUR_IST = 23
ENTRY_END_MINUTE_IST = 59

# ===================== SERVER CONFIG (Koyeb health check) =====================
PORT = int(os.environ.get("PORT", "8080"))

# ===================== BOT META =====================
BOT_NAME = "NoFap Streak Tracker"
