from __future__ import annotations

import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from common import config, database
from handlers_direct import router as direct_router
from handlers_general import router as general_router
from handlers_posts import router as posts_router
from handlers_text import router as text_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("telegram_publisher")

dp = Dispatcher()
dp.include_router(general_router)
dp.include_router(direct_router)
dp.include_router(posts_router)
dp.include_router(text_router)


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "ok": True,
            "service": "telegram-channel-publisher",
            "mode": "webhook",
            "scheduler_database": bool(database),
        }
    )


async def home(_: web.Request) -> web.Response:
    return web.Response(
        text="Telegram kanal postlari boti ishlamoqda.",
        content_type="text/plain",
    )


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]

    if database:
        await database.connect()
        await database.init_schema()
        log.info("PostgreSQL scheduler bazasi ulandi.")
    else:
        log.warning("DATABASE_URL yo'q: scheduler o'chirilgan.")

    await bot.set_webhook(
        url=config.webhook_url,
        allowed_updates=dp.resolve_used_update_types(),
        secret_token=config.webhook_secret,
        drop_pending_updates=False,
    )

    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s (%s)", me.username, me.id)
    log.info("Webhook: %s", config.webhook_url)
    log.info("Kanal: %s", config.channel_id)


async def on_shutdown(app: web.Application) -> None:
    if database:
        await database.close()
    log.info("Xizmat to'xtamoqda.")


def create_app() -> web.Application:
    bot = Bot(token=config.bot_token)
    app = web.Application()
    app["bot"] = bot

    app.router.add_get("/", home)
    app.router.add_get("/health", health)

    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True,
        secret_token=config.webhook_secret,
    ).register(app, path=config.webhook_path)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    web.run_app(
        create_app(),
        host="0.0.0.0",
        port=config.port,
        access_log=log,
    )
