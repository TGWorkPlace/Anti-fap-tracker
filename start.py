import asyncio
import logging
from aiohttp import web
from main import app, scheduler, setup_scheduler
from database import get_ist_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def health_check(request):
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
    logger.info("Health-check server live on port 8080")


async def main():
    # 1. Start health-check web server
    await start_web_server()

    # 2. Start Pyrogram using context manager (properly starts dispatcher)
    async with app:
        me = await app.get_me()
        logger.info(f"NoFap Bot live: @{me.username}")

        # 3. Start the APScheduler (5 AM IST broadcast)
        setup_scheduler()

        # 4. Keep alive inside the context manager so dispatcher stays running
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
