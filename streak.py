import os
import calendar
import datetime
import logging

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# ===================== PATHS =====================

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(MODULE_DIR, "streak_template.html")
IMG_DIR = os.path.join(MODULE_DIR, "img")
TMP_DIR = os.path.join(MODULE_DIR, "tmp")
DEFAULT_AVATAR_PATH = os.path.join(IMG_DIR, "default_avatar.png")

os.makedirs(TMP_DIR, exist_ok=True)

# Load the HTML template once at import time
with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    TEMPLATE_HTML = f.read()

WEEKDAY_LETTERS = ["S", "M", "T", "W", "T", "F", "S"]  # Sun..Sat


# ===================== ICON / FILE HELPERS =====================

def _file_uri(path: str) -> str:
    """Convert a local filesystem path into a file:// URI usable inside the HTML <img src>."""
    abs_path = os.path.abspath(path)
    return "file://" + abs_path


def _icon_for_answer(answer: str) -> str:
    """
    Maps a streak answer to its icon filename.
    answer: "yes" -> fire, "no" -> ice, None/missing -> blank (no icon)
    """
    if answer == "yes":
        return "fire.png"
    elif answer == "no":
        return "ice.png"
    return None  # blank day, no icon


# ===================== DATA FETCH HELPERS =====================

def _get_calendar_week_range(today: datetime.date) -> list:
    """
    Returns a list of 7 datetime.date objects for the Sun-Sat calendar week
    containing 'today'.
    Python's weekday(): Mon=0 ... Sun=6, so we adjust to make Sunday the start.
    """
    # Convert to "days since Sunday" offset
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - datetime.timedelta(days=days_since_sunday)
    return [week_start + datetime.timedelta(days=i) for i in range(7)]


def _build_streak_lookup(streak_entries: list) -> dict:
    """
    Converts a list of DB streak entry dicts (each with 'streak_date' as 'YYYY-MM-DD'
    and 'answer' as 'yes'/'no') into a dict: {date_str: answer}.
    """
    lookup = {}
    for entry in streak_entries:
        lookup[entry["streak_date"]] = entry["answer"]
    return lookup


# ===================== AVATAR HANDLING =====================

async def download_user_avatar(client, user_id: int) -> str:
    """
    Downloads the user's current Telegram profile photo fresh via Pyrogram.
    Returns a local file path. Falls back to a default avatar if unavailable.
    """
    try:
        dest_path = os.path.join(TMP_DIR, f"avatar_{user_id}.jpg")
        downloaded = await client.download_media(user_id, file_name=dest_path)
        if downloaded and os.path.exists(downloaded):
            return downloaded
    except Exception as e:
        logger.warning(f"Could not download avatar for user {user_id}: {e}")

    return DEFAULT_AVATAR_PATH if os.path.exists(DEFAULT_AVATAR_PATH) else None


# ===================== GRID BUILDERS =====================

def _build_weekly_grid_html(week_dates: list, streak_lookup: dict, today: datetime.date) -> str:
    """
    Builds the 7-column weekly grid HTML.
    - Past/today dates with a logged answer -> fire/ice icon
    - Future dates or dates with no entry -> blank (no icon)
    """
    cols = []
    for i, date_obj in enumerate(week_dates):
        date_str = date_obj.strftime("%Y-%m-%d")
        letter = WEEKDAY_LETTERS[i]
        day_num = date_obj.day

        answer = streak_lookup.get(date_str)
        icon_file = _icon_for_answer(answer)

        if icon_file:
            icon_html = f'<div class="icon-wrap"><img src="{_file_uri(os.path.join(IMG_DIR, icon_file))}" alt="icon"></div>'
        else:
            icon_html = '<div class="icon-wrap"></div>'

        col_html = f"""
        <div class="day-col">
          <div class="day-letter">{letter}</div>
          <div class="day-num">{day_num}</div>
          {icon_html}
        </div>
        """
        cols.append(col_html)

    return f'<div class="week-grid">{"".join(cols)}</div>'


def _build_monthly_grid_html(year: int, month: int, streak_lookup: dict) -> str:
    """
    Builds the monthly calendar grid HTML (Sun-Sat columns), including leading
    empty cells so the 1st of the month lands on the correct weekday column.
    """
    # Python's calendar module: Monday=0 by default. We want Sunday-first.
    cal = calendar.Calendar(firstweekday=6)  # 6 = Sunday
    month_days = cal.itermonthdates(year, month)

    cells = []
    for date_obj in month_days:
        if date_obj.month != month:
            cells.append('<div class="empty-cell"></div>')
            continue

        date_str = date_obj.strftime("%Y-%m-%d")
        answer = streak_lookup.get(date_str)
        icon_file = _icon_for_answer(answer)

        if icon_file:
            icon_html = f'<div class="icon-wrap"><img src="{_file_uri(os.path.join(IMG_DIR, icon_file))}" alt="icon"></div>'
        else:
            icon_html = ""

        cell_html = f"""
        <div class="day-cell">
          <div class="day-num">{date_obj.day}</div>
          {icon_html}
        </div>
        """
        cells.append(cell_html)

    weekday_row = '<div class="weekday-row">' + "".join(
        f"<div>{l}</div>" for l in WEEKDAY_LETTERS
    ) + "</div>"

    month_grid = f'<div class="month-grid">{"".join(cells)}</div>'

    return weekday_row + month_grid


# ===================== HTML ASSEMBLY =====================

def _render_full_html(
    mode: str,
    user_name: str,
    avatar_path: str,
    today: datetime.date,
    grid_html: str,
    total_streak: int,
) -> str:
    """
    Fills in the shared template with either weekly or monthly specific blocks.
    mode: "weekly" or "monthly"
    """
    avatar_src = _file_uri(avatar_path) if avatar_path else ""

    if mode == "weekly":
        title_class = "title-weekly"
        title_text = "ANTI-FAP-WEEKLY"
        subtitle_html = ""
        monthly_bg_flame = ""
    else:
        title_class = "title-monthly"
        title_text = "ANTI-FAP-MONTHLY"
        subtitle_html = '<div class="subtitle">BUILD DISCIPLINE. BREAK LIMITS.</div>'
        monthly_bg_flame = f'<img class="bg-flame" src="{_file_uri(os.path.join(IMG_DIR, "fire.png"))}" alt="">'

    html = TEMPLATE_HTML.format(
        monthly_bg_flame=monthly_bg_flame,
        avatar_src=avatar_src,
        user_name=user_name.upper(),
        title_class=title_class,
        title_text=title_text,
        subtitle_html=subtitle_html,
        grid_html=grid_html,
        img_dir=_file_uri(IMG_DIR),
        total_streak=total_streak,
        today_str=today.strftime("%b %d, %Y").upper(),
        day_name=today.strftime("%A").upper(),
        month_name=today.strftime("%B").upper(),
    )
    return html


# ===================== IMAGE RENDERING (Playwright) =====================

async def _html_to_png(html_content: str, output_path: str, width: int = 760, height: int = 900, scale: int = 3):
    """
    Renders the given HTML string to a PNG screenshot using headless Chromium.
    Only the .card element is screenshotted, so there's no extra blank canvas
    below the card (body has padding/gap for multi-card layouts, but each
    image request only ever renders a single card).

    device_scale_factor renders at `scale`x the CSS pixel density (like a
    Retina screenshot) so the output PNG is sharp on modern phone screens
    instead of soft/blurry 1x rendering.
    """
    tmp_html_path = output_path.replace(".png", ".html")
    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        try:
            page = await browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=scale,
            )
            await page.goto(_file_uri(tmp_html_path))
            await page.wait_for_timeout(150)  # allow images to fully paint
            card = page.locator(".card").first
            await card.screenshot(path=output_path)
        finally:
            await browser.close()

    try:
        os.remove(tmp_html_path)
    except OSError:
        pass

    return output_path


# ===================== PUBLIC ENTRYPOINTS =====================

async def generate_weekly_image(client, user_id: int, user_name: str, db) -> str:
    """
    Builds the weekly streak tracker image for a given user.
    Returns the path to the generated PNG.
    """
    today = datetime.datetime.now().date()
    week_dates = _get_calendar_week_range(today)

    start_str = week_dates[0].strftime("%Y-%m-%d")
    end_str = week_dates[-1].strftime("%Y-%m-%d")

    entries = db.get_streak_entries_in_range(user_id, start_str, end_str)
    streak_lookup = _build_streak_lookup(entries)

    grid_html = _build_weekly_grid_html(week_dates, streak_lookup, today)

    stats = db.get_user_stats(user_id) or {}
    total_streak = stats.get("current_streak", 0)

    avatar_path = await download_user_avatar(client, user_id)

    html_content = _render_full_html(
        mode="weekly",
        user_name=user_name,
        avatar_path=avatar_path,
        today=today,
        grid_html=grid_html,
        total_streak=total_streak,
    )

    output_path = os.path.join(TMP_DIR, f"weekly_{user_id}.png")
    return await _html_to_png(html_content, output_path)


async def generate_monthly_image(client, user_id: int, user_name: str, db) -> str:
    """
    Builds the monthly streak tracker image for a given user.
    Returns the path to the generated PNG.
    """
    today = datetime.datetime.now().date()
    year = today.year
    month = today.month

    month_start = datetime.date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    month_end = datetime.date(year, month, last_day)

    start_str = month_start.strftime("%Y-%m-%d")
    end_str = month_end.strftime("%Y-%m-%d")

    entries = db.get_streak_entries_in_range(user_id, start_str, end_str)
    streak_lookup = _build_streak_lookup(entries)

    grid_html = _build_monthly_grid_html(year, month, streak_lookup)

    stats = db.get_user_stats(user_id) or {}
    total_streak = stats.get("current_streak", 0)

    avatar_path = await download_user_avatar(client, user_id)

    html_content = _render_full_html(
        mode="monthly",
        user_name=user_name,
        avatar_path=avatar_path,
        today=today,
        grid_html=grid_html,
        total_streak=total_streak,
    )

    output_path = os.path.join(TMP_DIR, f"monthly_{user_id}.png")
    return await _html_to_png(html_content, output_path)
