from __future__ import annotations

import asyncio
import logging
import os

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import parse_chat_id
from db import Database, Post

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("publisher_scheduler")


async def send_post(bot: Bot, channel_id: int | str, post: Post):
    common = dict(
        chat_id=channel_id,
        caption=post.caption,
        caption_entities=post.entities,
        has_spoiler=post.has_spoiler,
        show_caption_above_media=post.show_caption_above_media,
    )
    if post.media_type == "photo":
        return await bot.send_photo(photo=post.file_id, **common)
    if post.media_type == "video":
        return await bot.send_video(
            video=post.file_id,
            supports_streaming=True,
            **common,
        )
    raise RuntimeError(f"Unsupported media type: {post.media_type}")


async def main() -> None:
    bot_token = os.environ["BOT_TOKEN"].strip()
    channel_id = parse_chat_id(os.environ["CHANNEL_ID"].strip())
    database_url = os.environ["DATABASE_URL"].strip()

    db = Database(database_url)
    await db.connect()
    await db.init_schema()
    bot = Bot(token=bot_token)

    try:
        due_posts = await db.claim_due_posts(limit=30)
        if not due_posts:
            log.info("Due scheduled posts: 0")
            return

        log.info("Due scheduled posts: %s", len(due_posts))

        for post in due_posts:
            try:
                sent = await send_post(bot, channel_id, post)
                await db.mark_published(post_id=post.id, message_id=sent.message_id)
                log.info("Published scheduled post #%s -> %s", post.id, sent.message_id)

                try:
                    await bot.send_message(
                        post.user_id,
                        "✅ Rejalashtirilgan post avtomatik joylandi.\n"
                        f"Post #{post.id} · Kanal xabar ID: {sent.message_id}",
                    )
                except TelegramAPIError:
                    log.warning("Could not notify user %s", post.user_id)

            except Exception as exc:
                log.exception("Scheduled post #%s failed", post.id)
                status, attempts = await db.scheduled_publish_failed(
                    post_id=post.id,
                    error=str(exc),
                    max_attempts=5,
                )

                if status == "failed":
                    try:
                        await bot.send_message(
                            post.user_id,
                            "❌ Rejalashtirilgan postni 5 urinishdan keyin ham "
                            "joylab bo'lmadi.\n"
                            f"Post #{post.id}\n"
                            f"Xato: {str(exc)[:500]}",
                        )
                    except TelegramAPIError:
                        pass
                else:
                    log.warning(
                        "Post #%s will retry on next cron run (attempt %s/5)",
                        post.id,
                        attempts,
                    )
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
