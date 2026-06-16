import asyncio
import logging
from aiohttp import web
from pyrogram import idle

from main import app, setup_scheduler
from database import get_ist_now

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


async def health_check(request):
    return web.json_response({
        "status": "ok",
        "service": "NoFap Streak Bot",
        "time_ist": get_ist_now().strftime("%d %b %Y %I:%M %p IST")
    })


async def start_web_server():
    web_app = web.Application()

    web_app.router.add_get("/", health_check)
    web_app.router.add_get("/health", health_check)

    runner = web.AppRunner(web_app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=8080
    )

    await site.start()

    logger.info("Health-check server running on port 8080")


async def main():
    try:
        # Health server
        await start_web_server()

        # Start bot
        await app.start()

        me = await app.get_me()

        logger.info(
            f"Bot started successfully: @{me.username} ({me.id})"
        )

        # Scheduler
        try:
            setup_scheduler()
            logger.info("Scheduler started")
        except Exception:
            logger.exception("Failed to start scheduler")

        # Keep bot alive
        await idle()

    except Exception:
        logger.exception("Fatal startup error")
        raise

    finally:
        try:
            await app.stop()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
