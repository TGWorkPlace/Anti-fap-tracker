import re
import json
import base64
import asyncio
import datetime
import logging

from pyrogram import enums, Client, filters, utils as pyroutils
from pyrogram.errors import ChatAdminRequired, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import your config
from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    ADMIN_IDS,
    IST,
    BROADCAST_HOUR_IST,
    BROADCAST_MINUTE_IST,
    ENTRY_START_HOUR_IST,
    ENTRY_START_MINUTE_IST,
    ENTRY_END_HOUR_IST,
    ENTRY_END_MINUTE_IST,
    PORT,
    BOT_NAME,
)
from database import Database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Fix chat ID constraints
pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999

db = Database()

class Bot(Client):
    def __init__(self):
        super().__init__(
            "nofap_streak_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
        )

    async def start(self):
        await super().start()
        logger.info("Bot session started.")
        await send_restart_notification(self)
        
        scheduler = AsyncIOScheduler()
        schedule_jobs(scheduler, self)
        
        await start_health_server()
        logger.info("All systems running.")

    async def stop(self, *args):
        logger.info("Bot stopping...")
        await super().stop()

# Initialize the Bot instance ONCE
app = Bot()

# ===================== HELPERS =====================

def get_ist_now() -> datetime.datetime:
    return datetime.datetime.now(IST)

def is_within_entry_window(now_ist: datetime.datetime) -> bool:
    start = now_ist.replace(hour=ENTRY_START_HOUR_IST, minute=ENTRY_START_MINUTE_IST, second=0, microsecond=0)
    end = now_ist.replace(hour=ENTRY_END_HOUR_IST, minute=ENTRY_END_MINUTE_IST, second=59, microsecond=999999)
    return start <= now_ist <= end

def streak_inline_keyboard(streak_date_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"streak_yes_{streak_date_str}"),
            InlineKeyboardButton("❌ No", callback_data=f"streak_no_{streak_date_str}"),
        ]
    ])

def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔵 Join the Streak", callback_data="join_streak")]])

# ===================== HANDLERS =====================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    text = f"✨ **Welcome to {BOT_NAME}** ✨\n\nTap the button below to begin."
    await message.reply_text(text, reply_markup=join_keyboard())

@app.on_message(filters.command("streak") & filters.private)
async def streak_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if not db.is_joined(user_id):
        await message.reply_text("Join first via /start")
        return
    stats = db.get_user_stats(user_id)
    await message.reply_text(f"🔥 Your Current Streak: {stats['current_streak']} day(s)")

@app.on_callback_query(filters.regex(r"^join_streak$"))
async def join_callback(client: Client, callback_query: CallbackQuery):
    if db.is_joined(callback_query.from_user.id):
        await callback_query.answer("Already joined!", show_alert=True)
        return
    db.add_user(user_id=callback_query.from_user.id, first_name=callback_query.from_user.first_name, username=callback_query.from_user.username)
    await callback_query.answer("✅ Joined successfully!", show_alert=True)

# ===================== SYSTEM FUNCTIONS =====================

async def send_restart_notification(client: Client):
    for admin_id in ADMIN_IDS:
        try:
            await client.send_message(admin_id, "🔄 **Bot Restarted Successfully**")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")

async def send_daily_streak_broadcast(client: Client):
    now_ist = get_ist_now()
    yesterday = now_ist - datetime.timedelta(days=1)
    streak_date_str = yesterday.strftime("%Y-%m-%d")
    user_ids = db.get_all_joined_users()
    
    for user_id in user_ids:
        try:
            await client.send_message(user_id, "🌅 **Good Morning! Did you succeed yesterday?**", reply_markup=streak_inline_keyboard(streak_date_str))
        except Exception as e:
            logger.error(f"Failed to broadcast to {user_id}: {e}")
        await asyncio.sleep(0.05)

def schedule_jobs(scheduler: AsyncIOScheduler, client: Client):
    scheduler.add_job(
        send_daily_streak_broadcast,
        trigger="cron",
        hour=BROADCAST_HOUR_IST,
        minute=BROADCAST_MINUTE_IST,
        timezone=IST,
        args=[client]
    )
    scheduler.start()

async def start_health_server():
    web_app = web.Application()
    web_app.router.add_get("/", lambda r: web.Response(text="OK"))
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

if __name__ == "__main__":
    app.run()
