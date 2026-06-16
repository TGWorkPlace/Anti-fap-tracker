import asyncio
import logging
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import BOT_TOKEN, API_ID, API_HASH
from database import (
    add_user, is_user_joined, get_all_active_users,
    save_streak, has_streak_entry_today, get_user_stats,
    get_ist_now, save_broadcast_record
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

app = Client(
    "nofap_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

scheduler = AsyncIOScheduler(timezone=IST)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_streak_date_for_broadcast() -> datetime:
    """The streak date is YESTERDAY (the day we're asking about)."""
    ist_now = get_ist_now()
    yesterday = ist_now - timedelta(days=1)
    return yesterday


def is_within_entry_window() -> bool:
    """Streak can be entered from 5:00 AM to 11:59 PM IST today."""
    ist_now = get_ist_now()
    start = ist_now.replace(hour=5, minute=0, second=0, microsecond=0)
    end = ist_now.replace(hour=23, minute=59, second=59, microsecond=0)
    return start <= ist_now <= end


def format_streak_date(dt: datetime) -> str:
    return dt.strftime("%d %B %Y")  # e.g. "16 June 2025"


def format_day_month(dt: datetime) -> str:
    return dt.strftime("%b %d")  # e.g. "Jun 16"


# ─────────────────────────────────────────────
# /START COMMAND
# ─────────────────────────────────────────────

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user = message.from_user
    join_button = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔥 Join the Challenge", callback_data="join_streak")
    ]])

    welcome_text = (
        "🧠 **Welcome to NoFap Streak Tracker** 🧠\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💪 *\"Discipline is choosing between what you want now*\n"
        "*and what you want most.\"*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌅 **Every morning at 5:00 AM IST**, I'll ask you:\n"
        "_\"Did you maintain your streak yesterday?\"_\n\n"
        "✅ Tap **YES** → Your streak grows stronger\n"
        "❌ Tap **NO** → Reset and rise again\n\n"
        "📊 Every response is saved with **date, month & time**\n"
        "📈 Track your **current streak** and **personal best**\n\n"
        "⏰ You have until **11:59 PM IST** each day to respond\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 **Ready to reclaim your power?**\n"
        "Hit the button below to begin your journey! 👇"
    )

    await message.reply_text(
        welcome_text,
        reply_markup=join_button,
        parse_mode="markdown"
    )


# ─────────────────────────────────────────────
# JOIN CALLBACK
# ─────────────────────────────────────────────

@app.on_callback_query(filters.regex("^join_streak$"))
async def join_callback(client: Client, callback: CallbackQuery):
    user = callback.from_user
    newly_added = add_user(user.id, user.username or "", user.first_name or "User")

    if newly_added:
        await callback.answer(
            "🔥 You joined the streak challenge! Stay strong!",
            show_alert=True
        )
        await callback.message.reply_text(
            f"✅ **Welcome aboard, {user.first_name}!**\n\n"
            "You're now part of the NoFap Streak community.\n\n"
            "🌅 Every morning at **5:00 AM IST**, you'll receive a check-in message.\n"
            "📅 Reply honestly — your journey starts **NOW**!\n\n"
            "💬 Use /stats to see your progress anytime.",
            parse_mode="markdown"
        )
    else:
        await callback.answer(
            "✅ You're already in the challenge! Keep going! 💪",
            show_alert=True
        )


# ─────────────────────────────────────────────
# STREAK RESPONSE CALLBACKS
# ─────────────────────────────────────────────

@app.on_callback_query(filters.regex("^streak_(yes|no)$"))
async def streak_response_callback(client: Client, callback: CallbackQuery):
    user = callback.from_user

    if not is_user_joined(user.id):
        await callback.answer(
            "❌ You haven't joined yet! Send /start to join.",
            show_alert=True
        )
        return

    if not is_within_entry_window():
        await callback.answer(
            "⏰ Time's up! Streak window closed at 11:59 PM IST.",
            show_alert=True
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    streak_date = get_streak_date_for_broadcast()

    if has_streak_entry_today(user.id, streak_date):
        await callback.answer(
            f"📌 You already submitted your streak for {format_day_month(streak_date)}!",
            show_alert=True
        )
        return

    maintained = callback.data == "streak_yes"
    saved = save_streak(user.id, streak_date, maintained)

    if saved:
        if maintained:
            await callback.answer(
                f"✅ Streak for {format_day_month(streak_date)} added successfully! Keep it up! 🔥",
                show_alert=True
            )
            stats = get_user_stats(user.id)
            await callback.message.edit_text(
                f"🔥 **Streak Logged — {format_streak_date(streak_date)}**\n\n"
                f"✅ You maintained your NoFap streak!\n\n"
                f"📊 **Your Stats:**\n"
                f"├ 🔥 Current Streak: **{stats['current_streak']} days**\n"
                f"├ 🏆 Longest Streak: **{stats['longest_streak']} days**\n"
                f"└ 📅 Total Days Logged: **{stats['total_streaks']}**\n\n"
                f"💪 *Keep pushing. You're stronger than you think.*",
                parse_mode="markdown"
            )
        else:
            await callback.answer(
                f"💔 Streak ended. Entry recorded for {format_day_month(streak_date)}. Rise again!",
                show_alert=True
            )
            await callback.message.edit_text(
                f"📋 **Streak Entry — {format_streak_date(streak_date)}**\n\n"
                f"❌ Streak not maintained.\n\n"
                f"🌱 *Every fall is a chance to rise stronger.*\n"
                f"*Today is a brand new beginning.*\n\n"
                f"🔄 Tomorrow's check-in is a fresh start!",
                parse_mode="markdown"
            )
    else:
        await callback.answer(
            "⚠️ Something went wrong. Please try again.",
            show_alert=True
        )


# ─────────────────────────────────────────────
# EXPIRED STREAK CALLBACK (outside window)
# ─────────────────────────────────────────────

@app.on_callback_query(filters.regex("^streak_expired$"))
async def expired_callback(client: Client, callback: CallbackQuery):
    await callback.answer(
        "⏰ Streak ended! The entry window has closed for today.",
        show_alert=True
    )
    try:
        await callback.message.delete()
    except Exception:
        pass


# ─────────────────────────────────────────────
# /STATS COMMAND
# ─────────────────────────────────────────────

@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    user = message.from_user
    if not is_user_joined(user.id):
        await message.reply_text(
            "❌ You haven't joined the challenge yet!\nSend /start to begin your journey.",
            parse_mode="markdown"
        )
        return

    stats = get_user_stats(user.id)
    joined_str = stats["joined_at"].strftime("%d %B %Y") if stats.get("joined_at") else "Unknown"

    await message.reply_text(
        f"📊 **Your NoFap Stats, {stats['first_name']}!**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 **Current Streak:** {stats['current_streak']} days\n"
        f"🏆 **Longest Streak:** {stats['longest_streak']} days\n"
        f"📅 **Total Days Logged:** {stats['total_streaks']}\n"
        f"📆 **Member Since:** {joined_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💪 *Keep going. Every day counts.*",
        parse_mode="markdown"
    )


# ─────────────────────────────────────────────
# MORNING BROADCAST (5 AM IST)
# ─────────────────────────────────────────────

async def send_morning_broadcast():
    """Broadcast streak check-in to all active users at 5 AM IST."""
    ist_now = get_ist_now()
    streak_date = ist_now - timedelta(days=1)  # Yesterday = the streak date
    date_label = format_streak_date(streak_date)
    day_month = format_day_month(streak_date)

    broadcast_text = (
        f"🌅 **Good Morning! Daily Streak Check-In**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 **Streak Date: {date_label}**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🧠 *Did you maintain your NoFap streak*\n"
        f"*on **{day_month}**?*\n\n"
        f"⏰ You have until **11:59 PM IST today** to respond.\n"
        f"After that, the window closes!\n\n"
        f"💬 Be honest with yourself — that's where growth begins."
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ YES — I maintained it!", callback_data="streak_yes"),
        InlineKeyboardButton("❌ NO — I slipped", callback_data="streak_no")
    ]])

    users = get_all_active_users()
    sent_ids = []

    for user in users:
        uid = user["user_id"]
        try:
            msg = await app.send_message(uid, broadcast_text, reply_markup=keyboard, parse_mode="markdown")
            sent_ids.append({"user_id": uid, "message_id": msg.id})
            await asyncio.sleep(0.05)  # Rate limit safety
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except (UserIsBlocked, InputUserDeactivated):
            logger.warning(f"User {uid} blocked or deactivated. Skipping.")
        except Exception as e:
            logger.error(f"Failed to send to {uid}: {e}")

    save_broadcast_record(streak_date, sent_ids)
    logger.info(f"Morning broadcast sent to {len(sent_ids)} users for {date_label}")


# ─────────────────────────────────────────────
# SCHEDULER SETUP
# ─────────────────────────────────────────────

def setup_scheduler():
    scheduler.add_job(
        send_morning_broadcast,
        CronTrigger(hour=5, minute=0, timezone=IST),
        id="morning_broadcast",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started — morning broadcast at 5:00 AM IST daily.")


# ─────────────────────────────────────────────
# BOT STARTUP / SHUTDOWN
# ─────────────────────────────────────────────

async def main():
    setup_scheduler()
    await app.start()
    me = await app.get_me()
    logger.info(f"Bot started: @{me.username}")
    await asyncio.Event().wait()  # Keep running


if __name__ == "__main__":
    asyncio.run(main())
