import datetime
import pymongo
from pymongo import MongoClient, ReturnDocument

from config import MONGO_URI, DB_NAME, IST


class Database:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[DB_NAME]

        # Collections
        self.users = self.db["users"]          # joined users list
        self.streaks = self.db["streaks"]       # every daily streak entry (full history)

        # Helpful indexes
        self.users.create_index("user_id", unique=True)
        self.streaks.create_index([("user_id", 1), ("streak_date", 1)], unique=True)

    # ===================== USER / JOIN MANAGEMENT =====================

    def is_joined(self, user_id: int) -> bool:
        return self.users.find_one({"user_id": user_id}) is not None

    def add_user(self, user_id: int, first_name: str, username: str = None):
        """Add user to joined list if not already present. Returns True if newly added."""
        existing = self.users.find_one({"user_id": user_id})
        if existing:
            return False

        now_ist = datetime.datetime.now(IST)
        self.users.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "username": username,
            "joined_at": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
            "joined_date": now_ist.strftime("%Y-%m-%d"),
            "current_streak": 0,
            "longest_streak": 0,
            "last_yes_date": None,   # last date (YYYY-MM-DD) user confirmed "Yes"
            "total_yes": 0,
            "total_no": 0,
        })
        return True

    def get_all_joined_users(self):
        """Returns list of all joined user_ids."""
        return [u["user_id"] for u in self.users.find({}, {"user_id": 1})]

    def get_user(self, user_id: int):
        return self.users.find_one({"user_id": user_id})

    def get_total_users_count(self) -> int:
        return self.users.count_documents({})

    # ===================== STREAK ENTRY MANAGEMENT =====================

    def has_entry_for_date(self, user_id: int, streak_date: str) -> bool:
        """streak_date format: YYYY-MM-DD (the date being reported on, i.e. 'yesterday')."""
        return self.streaks.find_one({"user_id": user_id, "streak_date": streak_date}) is not None

    def add_streak_entry(self, user_id: int, streak_date: str, answer: str, day_name: str, month_name: str):
        """
        Records a single day's streak answer permanently in history.
        answer: "yes" or "no"
        streak_date: YYYY-MM-DD of the day being reported on
        """
        now_ist = datetime.datetime.now(IST)

        entry = {
            "user_id": user_id,
            "streak_date": streak_date,
            "day_name": day_name,
            "month_name": month_name,
            "answer": answer,
            "answered_at": now_ist.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.streaks.insert_one(entry)

        # Update user's running stats
        user = self.users.find_one({"user_id": user_id})
        if not user:
            return entry

        if answer == "yes":
            new_current_streak = user.get("current_streak", 0) + 1
            new_longest_streak = max(user.get("longest_streak", 0), new_current_streak)
            self.users.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "current_streak": new_current_streak,
                        "longest_streak": new_longest_streak,
                        "last_yes_date": streak_date,
                    },
                    "$inc": {"total_yes": 1},
                }
            )
        else:
            # "No" is just logged, counter is NOT reset, per requirement.
            self.users.update_one(
                {"user_id": user_id},
                {"$inc": {"total_no": 1}}
            )

        return entry

    def get_user_history(self, user_id: int, limit: int = 30):
        """Returns most recent streak entries for a user, newest first."""
        cursor = self.streaks.find({"user_id": user_id}).sort("streak_date", -1).limit(limit)
        return list(cursor)

    def get_streak_entries_in_range(self, user_id: int, start_date: str, end_date: str):
        """
        Returns all streak entries for a user between start_date and end_date
        (inclusive), both in 'YYYY-MM-DD' string format. Used by /weekly and
        /monthly image generation to look up which days were Yes/No/blank.
        Since dates are zero-padded 'YYYY-MM-DD' strings, lexicographic
        comparison is equivalent to chronological comparison.
        """
        cursor = self.streaks.find({
            "user_id": user_id,
            "streak_date": {"$gte": start_date, "$lte": end_date},
        })
        return list(cursor)

    def get_user_stats(self, user_id: int):
        user = self.users.find_one({"user_id": user_id})
        if not user:
            return None

        total_entries = self.streaks.count_documents({"user_id": user_id})
        return {
            "current_streak": user.get("current_streak", 0),
            "longest_streak": user.get("longest_streak", 0),
            "total_yes": user.get("total_yes", 0),
            "total_no": user.get("total_no", 0),
            "total_entries": total_entries,
            "joined_at": user.get("joined_at"),
        }
