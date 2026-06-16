from pymongo import MongoClient, ASCENDING
from datetime import datetime, timedelta, timezone
import pytz
from config import MONGO_URI, DB_NAME

IST = pytz.timezone("Asia/Kolkata")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]

users_col = db["users"]
streaks_col = db["streaks"]
broadcasts_col = db["broadcasts"]

# Indexes
users_col.create_index([("user_id", ASCENDING)], unique=True)
streaks_col.create_index([("user_id", ASCENDING), ("streak_date", ASCENDING)], unique=True)
broadcasts_col.create_index([("broadcast_date", ASCENDING)], unique=True)


def get_ist_now() -> datetime:
    return datetime.now(IST)


def add_user(user_id: int, username: str, first_name: str) -> bool:
    """Add user to joined list. Returns True if newly added."""
    existing = users_col.find_one({"user_id": user_id})
    if existing:
        return False
    users_col.insert_one({
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "joined_at": get_ist_now(),
        "total_streaks": 0,
        "current_streak": 0,
        "longest_streak": 0,
        "is_active": True
    })
    return True


def is_user_joined(user_id: int) -> bool:
    return users_col.find_one({"user_id": user_id, "is_active": True}) is not None


def get_all_active_users() -> list:
    return list(users_col.find({"is_active": True}))


def save_streak(user_id: int, streak_date: datetime, maintained: bool) -> bool:
    """
    Save streak for a specific date.
    streak_date: The date the streak is FOR (previous day).
    Returns True if saved, False if already exists.
    """
    date_only = streak_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    existing = streaks_col.find_one({"user_id": user_id, "streak_date": date_only})
    if existing:
        return False

    ist_now = get_ist_now()
    streaks_col.insert_one({
        "user_id": user_id,
        "streak_date": date_only,
        "year": date_only.year,
        "month": date_only.month,
        "month_name": date_only.strftime("%B"),
        "day": date_only.day,
        "maintained": maintained,
        "recorded_at": ist_now,
        "recorded_at_ist_str": ist_now.strftime("%d %b %Y %I:%M %p IST")
    })

    if maintained:
        users_col.update_one({"user_id": user_id}, {"$inc": {"total_streaks": 1}})
        _update_streak_counts(user_id)

    return True


def _update_streak_counts(user_id: int):
    """Recalculate current and longest streak for a user."""
    records = list(streaks_col.find(
        {"user_id": user_id, "maintained": True},
        sort=[("streak_date", ASCENDING)]
    ))
    if not records:
        users_col.update_one({"user_id": user_id}, {"$set": {"current_streak": 0, "longest_streak": 0}})
        return

    dates = [r["streak_date"] for r in records]
    longest = 1
    current = 1
    temp = 1
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        if delta == 1:
            temp += 1
            if temp > longest:
                longest = temp
        else:
            temp = 1

    # Current streak: check if it's consecutive up to yesterday or today
    ist_today = get_ist_now().date()
    last_date = dates[-1].date()
    if (ist_today - last_date).days <= 1:
        current = temp
    else:
        current = 0

    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"current_streak": current, "longest_streak": longest}}
    )


def has_streak_entry_today(user_id: int, streak_date: datetime) -> bool:
    """Check if user already submitted streak for a given date."""
    date_only = streak_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    return streaks_col.find_one({"user_id": user_id, "streak_date": date_only}) is not None


def get_user_stats(user_id: int) -> dict:
    user = users_col.find_one({"user_id": user_id})
    if not user:
        return {}
    return {
        "first_name": user.get("first_name", "User"),
        "total_streaks": user.get("total_streaks", 0),
        "current_streak": user.get("current_streak", 0),
        "longest_streak": user.get("longest_streak", 0),
        "joined_at": user.get("joined_at")
    }


def save_broadcast_record(broadcast_date: datetime, message_ids: list):
    """Save a record of who received the morning broadcast."""
    date_only = broadcast_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    broadcasts_col.update_one(
        {"broadcast_date": date_only},
        {"$set": {"message_ids": message_ids, "sent_at": get_ist_now()}},
        upsert=True
    )


def get_broadcast_record(broadcast_date: datetime) -> dict:
    date_only = broadcast_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    return broadcasts_col.find_one({"broadcast_date": date_only}) or {}
