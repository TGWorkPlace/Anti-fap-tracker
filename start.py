"""
Health-check web server for Koyeb (port 8080).
Runs alongside the Pyrogram bot using asyncio.
"""
import asyncio
import logging
from aiohttp import web
from main import app, setup_scheduler
import pytz

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")


async def health_check(request):
    from database import get_ist_now
    now = get_ist_now().strftime("%d %b %Y %I:%M %p IST")
    return web.json_response({
        "status": "ok",
        "service": "NoFap Streak Bot",
        "time_ist": now
    })


async def start_web_server():
    web_app = web.Application()
    web_app.router.add_get("/", health_check)
    web_app.router.add_get("/health", health_check)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Health-check server running on port 8080")


async def main():
    setup_scheduler()
    await start_web_server()
    await app.start()
    me = await app.get_me()
    logger.info(f"NoFap Bot live: @{me.username}")
    await asyncio.Event().wait()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
