import re
import os
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
import streak as streak_image

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
        schedule_jobs(scheduler)

        await start_health_server()
        logger.info("All systems running.")

    async def stop(self, *args):
        logger.info("Bot stopping...")
        await super().stop()


# Initialize the Bot instance ONCE
app = Bot()

# ===================== TEXT TEMPLATES =====================

START_TEXT = """✨ **Welcome to {bot_name}** ✨

🔥 You are one decision away from a stronger, sharper, more disciplined version of yourself.

Every streak you build is proof that you are in control — not your urges, not your impulses. **You.**

🧠 **What this bot does for you:**
• Tracks your daily NoFap streak automatically
• Sends you a daily check-in every morning at **5:00 AM IST**
• Builds your discipline one day at a time
• Keeps a permanent record of your journey

💪 Champions are not born. They are built — one single day of discipline, repeated.

👇 Tap the button below to begin your transformation. Your future self is waiting.
"""

JOIN_BUTTON_TEXT = "🔵 Join the Streak"
JOIN_ALERT_TEXT = "✅ You joined to streak! Your journey starts now. 💪"
ALREADY_JOINED_TEXT = "You're already part of the streak family! 🔥 Use /streak to check your progress."

STREAK_ENDED_ALERT = "⏰ Streak ended! The time limit to answer has passed."

ENTRY_SAVED_ALERT = "✅ Added successfully!"
ALREADY_ANSWERED_ALERT = "ℹ️ You've already answered for this day."


# ===================== HELPERS =====================

def get_ist_now() -> datetime.datetime:
    return datetime.datetime.now(IST)


def is_within_entry_window(now_ist: datetime.datetime) -> bool:
    """Entry window is from ENTRY_START to ENTRY_END (same day), IST."""
    start = now_ist.replace(
        hour=ENTRY_START_HOUR_IST, minute=ENTRY_START_MINUTE_IST, second=0, microsecond=0
    )
    end = now_ist.replace(
        hour=ENTRY_END_HOUR_IST, minute=ENTRY_END_MINUTE_IST, second=59, microsecond=999999
    )
    return start <= now_ist <= end


def format_streak_question(target_date: datetime.datetime) -> str:
    day_str = target_date.strftime("%d")
    month_str = target_date.strftime("%B")
    day_name = target_date.strftime("%A")

    text = f"""🌅 **Good Morning, Warrior!**

📅 **{day_name}, {month_str} {day_str}**

Did you successfully complete your NoFap streak for **{month_str} {day_str}**?

🕒 You have until **11:59 PM IST today** to respond. After that, the window closes for this entry.

Answer honestly — this streak is for you, not anyone else. 💪
"""
    return text


def streak_inline_keyboard(streak_date_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"streak_yes_{streak_date_str}"),
                InlineKeyboardButton("❌ No", callback_data=f"streak_no_{streak_date_str}"),
            ]
        ]
    )


def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(JOIN_BUTTON_TEXT, callback_data="join_streak")]]
    )


# ===================== COMMAND HANDLERS =====================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    text = START_TEXT.format(bot_name=BOT_NAME)
    await message.reply_text(
        text,
        reply_markup=join_keyboard(),
        disable_web_page_preview=True,
    )


@app.on_message(filters.command("streak") & filters.private)
async def streak_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if not db.is_joined(user_id):
        await message.reply_text(
            "You haven't joined yet! Tap /start and hit the join button first. 🔵"
        )
        return

    stats = db.get_user_stats(user_id)
    if not stats:
        await message.reply_text("No streak data found yet. Start answering daily check-ins!")
        return

    text = f"""🔥 **Your Current Streak**

🏆 Current Streak: **{stats['current_streak']} day(s)**
⭐ Longest Streak: **{stats['longest_streak']} day(s)**

Keep going — discipline compounds. 💪
"""
    await message.reply_text(text)


@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if not db.is_joined(user_id):
        await message.reply_text(
            "You haven't joined yet! Tap /start and hit the join button first. 🔵"
        )
        return

    stats = db.get_user_stats(user_id)
    if not stats:
        await message.reply_text("No streak data found yet. Start answering daily check-ins!")
        return

    history = db.get_user_history(user_id, limit=10)
    history_lines = []
    for entry in history:
        emoji = "✅" if entry["answer"] == "yes" else "❌"
        history_lines.append(f"{emoji} {entry['day_name']}, {entry['month_name']} {entry['streak_date'][-2:]}")

    history_text = "\n".join(history_lines) if history_lines else "No entries yet."

    text = f"""📊 **Your Full Stats**

🏆 Current Streak: **{stats['current_streak']} day(s)**
⭐ Longest Streak: **{stats['longest_streak']} day(s)**
✅ Total "Yes": **{stats['total_yes']}**
❌ Total "No": **{stats['total_no']}**
📅 Joined on: **{stats['joined_at']}**

🗓 **Last 10 Entries:**
{history_text}
"""
    await message.reply_text(text)


@app.on_message(filters.command("weekly") & filters.private)
async def weekly_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if not db.is_joined(user_id):
        await message.reply_text(
            "You haven't joined yet! Tap /start and hit the join button first. 🔵"
        )
        return

    status_msg = await message.reply_text("⏳ Generating your weekly streak card...")

    user_name = message.from_user.first_name or "User"
    image_path = None

    try:
        image_path = await streak_image.generate_weekly_image(client, user_id, user_name, db)
        await message.reply_photo(photo=image_path, caption="🔥 **Your Weekly Streak Tracker**")
    except Exception as e:
        logger.error(f"Failed to generate weekly image for {user_id}: {e}")
        await message.reply_text("⚠️ Something went wrong generating your weekly card. Please try again.")
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass
        # Clean up the generated file from disk after sending
        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
        except Exception:
            pass


@app.on_message(filters.command("monthly") & filters.private)
async def monthly_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if not db.is_joined(user_id):
        await message.reply_text(
            "You haven't joined yet! Tap /start and hit the join button first. 🔵"
        )
        return

    status_msg = await message.reply_text("⏳ Generating your monthly streak card...")

    user_name = message.from_user.first_name or "User"
    image_path = None

    try:
        image_path = await streak_image.generate_monthly_image(client, user_id, user_name, db)
        await message.reply_photo(photo=image_path, caption="🔥 **Your Monthly Streak Tracker**")
    except Exception as e:
        logger.error(f"Failed to generate monthly image for {user_id}: {e}")
        await message.reply_text("⚠️ Something went wrong generating your monthly card. Please try again.")
    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass
        # Clean up the generated file from disk after sending
        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
        except Exception:
            pass


@app.on_message(filters.command("broadcaststats") & filters.private)
async def broadcast_stats_handler(client: Client, message: Message):
    """Admin only: quick check of total joined users."""
    if message.from_user.id not in ADMIN_IDS:
        return
    total = db.get_total_users_count()
    await message.reply_text(f"👥 Total joined users: **{total}**")


# ===================== CALLBACK HANDLERS =====================

@app.on_callback_query(filters.regex(r"^join_streak$"))
async def join_callback(client: Client, callback_query: CallbackQuery):
    user = callback_query.from_user

    if db.is_joined(user.id):
        await callback_query.answer(ALREADY_JOINED_TEXT, show_alert=True)
        return

    db.add_user(user_id=user.id, first_name=user.first_name or "", username=user.username)
    await callback_query.answer(JOIN_ALERT_TEXT, show_alert=True)


@app.on_callback_query(filters.regex(r"^streak_(yes|no)_\d{4}-\d{2}-\d{2}$"))
async def streak_answer_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data  # e.g. streak_yes_2026-06-16
    parts = data.split("_")
    answer = parts[1]               # "yes" or "no"
    streak_date_str = parts[2]      # "2026-06-16"

    now_ist = get_ist_now()

    # Check time window first
    if not is_within_entry_window(now_ist):
        await callback_query.answer(STREAK_ENDED_ALERT, show_alert=True)
        try:
            await callback_query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete expired streak message: {e}")
        return

    # Check if already answered for this date
    if db.has_entry_for_date(user_id, streak_date_str):
        await callback_query.answer(ALREADY_ANSWERED_ALERT, show_alert=True)
        return

    # Parse date to get day_name / month_name for storage
    streak_date_obj = datetime.datetime.strptime(streak_date_str, "%Y-%m-%d")
    day_name = streak_date_obj.strftime("%A")
    month_name = streak_date_obj.strftime("%B")

    db.add_streak_entry(
        user_id=user_id,
        streak_date=streak_date_str,
        answer=answer,
        day_name=day_name,
        month_name=month_name,
    )

    await callback_query.answer(ENTRY_SAVED_ALERT, show_alert=True)

    # Edit message to show it's been answered (prevents repeated taps visually)
    try:
        emoji = "✅" if answer == "yes" else "❌"
        new_text = callback_query.message.text + f"\n\n{emoji} **You answered: {answer.upper()}**"
        await callback_query.message.edit_text(new_text)
    except Exception as e:
        logger.warning(f"Failed to edit answered streak message: {e}")


# ===================== SYSTEM FUNCTIONS =====================

async def send_restart_notification(client: Client):
    for admin_id in ADMIN_IDS:
        try:
            await client.send_message(admin_id, "🔄 **Bot Restarted Successfully**")
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def send_daily_streak_broadcast():
    """
    Runs every day at 5:00 AM IST.
    Asks about YESTERDAY's date (the day that just ended).
    """
    now_ist = get_ist_now()
    yesterday = now_ist - datetime.timedelta(days=1)
    streak_date_str = yesterday.strftime("%Y-%m-%d")

    text = format_streak_question(yesterday)
    keyboard = streak_inline_keyboard(streak_date_str)

    user_ids = db.get_all_joined_users()
    logger.info(f"Starting daily broadcast for {streak_date_str} to {len(user_ids)} users.")

    success_count = 0
    fail_count = 0

    for user_id in user_ids:
        try:
            await app.send_message(user_id, text, reply_markup=keyboard)
            success_count += 1
        except FloodWait as e:
            logger.warning(f"FloodWait {e.value}s while broadcasting to {user_id}")
            await asyncio.sleep(e.value)
            try:
                await app.send_message(user_id, text, reply_markup=keyboard)
                success_count += 1
            except Exception as inner_e:
                logger.error(f"Failed to send to {user_id} after FloodWait: {inner_e}")
                fail_count += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast to {user_id}: {e}")
            fail_count += 1

        # Small delay to avoid hitting flood limits on large user bases
        await asyncio.sleep(0.05)

    logger.info(
        f"Daily broadcast complete. Success: {success_count}, Failed: {fail_count}."
    )


def schedule_jobs(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        send_daily_streak_broadcast,
        trigger="cron",
        hour=BROADCAST_HOUR_IST,
        minute=BROADCAST_MINUTE_IST,
        timezone=IST,
        id="daily_streak_broadcast",
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started. Daily broadcast set for {BROADCAST_HOUR_IST:02d}:{BROADCAST_MINUTE_IST:02d} IST."
    )


# ===================== HEALTH CHECK SERVER (Koyeb) =====================

async def health_check(request):
    return web.Response(text="OK - NoFap Streak Bot is running.")


async def start_health_server():
    web_app = web.Application()
    web_app.router.add_get("/", health_check)
    web_app.router.add_get("/health", health_check)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health check server running on port {PORT}.")


# ===================== MAIN ENTRYPOINT =====================

if __name__ == "__main__":
    app.run()
