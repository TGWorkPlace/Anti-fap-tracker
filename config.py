import os

# Bot Configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH_HERE")

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "nofap_bot"

# Bot Settings
BOT_USERNAME = os.environ.get("BOT_USERNAME", "YourBotUsername")
STREAK_BROADCAST_HOUR = 5    # 5 AM IST
STREAK_BROADCAST_MINUTE = 0
IST_OFFSET = 5.5             # UTC+5:30

# Streak entry window: 5:00 AM to 11:59 PM IST same day
STREAK_WINDOW_START_HOUR = 5
STREAK_WINDOW_END_HOUR = 23
STREAK_WINDOW_END_MINUTE = 59
