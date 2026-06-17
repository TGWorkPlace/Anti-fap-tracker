import hmac
import hashlib
import json
import time
import calendar
import datetime
from urllib.parse import parse_qsl

from config import BOT_TOKEN, IST

WEEKDAY_LETTERS = ["S", "M", "T", "W", "T", "F", "S"]  # Sun..Sat

# How old (in seconds) an initData payload is allowed to be before we reject it.
# Telegram's own docs recommend checking auth_date; 24 hours is a reasonable
# generous window for a Mini App that may stay open in a background tab.
MAX_INIT_DATA_AGE_SECONDS = 86400


# ===================== INIT DATA VERIFICATION =====================

def verify_init_data(init_data: str) -> dict:
    """
    Verifies the authenticity of a Telegram WebApp initData string per
    Telegram's official validation algorithm:
      https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app

    Returns the parsed user dict if valid, otherwise raises ValueError.
    """
    if not init_data:
        raise ValueError("Empty init_data")

    # parse_qsl preserves duplicate keys and does NOT url-decode twice
    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing hash in init_data")

    # Build the data-check-string: all remaining fields sorted alphabetically,
    # joined as key=value with '\n' separators.
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data.items())
    )

    # secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=BOT_TOKEN.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    # computed_hash = HMAC_SHA256(key=secret_key, msg=data_check_string) as hex
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("Invalid init_data signature")

    # Optional freshness check using auth_date
    auth_date = data.get("auth_date")
    if auth_date:
        age = time.time() - int(auth_date)
        if age > MAX_INIT_DATA_AGE_SECONDS:
            raise ValueError("init_data has expired")

    user_raw = data.get("user")
    if not user_raw:
        raise ValueError("Missing user field in init_data")

    user = json.loads(user_raw)
    return user


# ===================== DATE / ICON HELPERS =====================

def _icon_key_for_answer(answer: str) -> str:
    """Maps a streak answer to a frontend-facing icon key: 'fire', 'ice', or None (blank)."""
    if answer == "yes":
        return "fire"
    elif answer == "no":
        return "ice"
    return None


def _get_calendar_week_range(today: datetime.date) -> list:
    """Returns 7 datetime.date objects for the Sun-Sat calendar week containing 'today'."""
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - datetime.timedelta(days=days_since_sunday)
    return [week_start + datetime.timedelta(days=i) for i in range(7)]


def _build_streak_lookup(streak_entries: list) -> dict:
    return {entry["streak_date"]: entry["answer"] for entry in streak_entries}


# ===================== PUBLIC DATA BUILDERS =====================

def build_weekly_payload(user_id: int, db) -> dict:
    """
    Builds the JSON-serializable payload describing the current Sun-Sat week
    for a given user: per-day icon state, plus footer stats.
    """
    now_ist = datetime.datetime.now(IST)
    today = now_ist.date()
    week_dates = _get_calendar_week_range(today)

    start_str = week_dates[0].strftime("%Y-%m-%d")
    end_str = week_dates[-1].strftime("%Y-%m-%d")

    entries = db.get_streak_entries_in_range(user_id, start_str, end_str)
    streak_lookup = _build_streak_lookup(entries)

    days = []
    for i, date_obj in enumerate(week_dates):
        date_str = date_obj.strftime("%Y-%m-%d")
        answer = streak_lookup.get(date_str)
        days.append({
            "letter": WEEKDAY_LETTERS[i],
            "day_num": date_obj.day,
            "date": date_str,
            "icon": _icon_key_for_answer(answer),
        })

    stats = db.get_user_stats(user_id) or {}

    return {
        "days": days,
        "total_streak": stats.get("current_streak", 0),
        "today_str": today.strftime("%b %d, %Y").upper(),
        "day_name": today.strftime("%A").upper(),
        "month_name": today.strftime("%B").upper(),
    }


def build_monthly_payload(user_id: int, db) -> dict:
    """
    Builds the JSON-serializable payload describing the current calendar month
    for a given user: per-day icon state (with leading blanks for alignment),
    plus footer stats.
    """
    now_ist = datetime.datetime.now(IST)
    today = now_ist.date()
    year, month = today.year, today.month

    month_start = datetime.date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = datetime.date(year, month, last_day)

    start_str = month_start.strftime("%Y-%m-%d")
    end_str = month_end.strftime("%Y-%m-%d")

    entries = db.get_streak_entries_in_range(user_id, start_str, end_str)
    streak_lookup = _build_streak_lookup(entries)

    cal = calendar.Calendar(firstweekday=6)  # Sunday-first
    cells = []
    for date_obj in cal.itermonthdates(year, month):
        if date_obj.month != month:
            cells.append({"empty": True})
            continue

        date_str = date_obj.strftime("%Y-%m-%d")
        answer = streak_lookup.get(date_str)
        cells.append({
            "empty": False,
            "day_num": date_obj.day,
            "date": date_str,
            "icon": _icon_key_for_answer(answer),
        })

    stats = db.get_user_stats(user_id) or {}

    return {
        "cells": cells,
        "total_streak": stats.get("current_streak", 0),
        "today_str": today.strftime("%b %d, %Y").upper(),
        "day_name": today.strftime("%A").upper(),
        "month_name": today.strftime("%B").upper(),
    }


def build_user_payload(user: dict) -> dict:
    """
    Builds the user-identity portion of the payload (name + avatar URL) from
    the verified Telegram user dict found in initData.
    Note: Telegram's initData user object does NOT include a profile photo
    URL by default, so the frontend falls back to a default avatar unless a
    photo_url happens to be present (only included for some auth contexts).
    """
    first_name = user.get("first_name", "User")
    last_name = user.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    return {
        "user_id": user.get("id"),
        "name": full_name.upper(),
        "photo_url": user.get("photo_url"),  # may be None
    }
