from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from contextlib import suppress

from aiohttp import web
from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, ForceReply, Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import Config, load_config
from keyboards import preview_keyboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("render_telegram_publisher")

config: Config = load_config()
router = Router()
dp = Dispatcher()
dp.include_router(router)

# Prevent two rapid publish callbacks for the same preview from creating duplicates.
_publish_locks: dict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)
_published_in_process: set[tuple[int, int]] = set()

EDIT_REF_RE = re.compile(r"^PUBLISHER_EDIT_REF:(-?\d+):(\d+)$")


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in config.admin_ids


async def deny(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    await message.answer(
        "⛔ You are not authorized to use this bot.\n"
        f"Your Telegram ID: <code>{user_id}</code>",
        parse_mode="HTML",
    )


def media_kind(message: Message) -> str | None:
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    return None


async def send_media(
    *,
    bot: Bot,
    chat_id: int | str,
    source: Message,
    reply_markup=None,
) -> Message:
    """Send a photo/video using Telegram's existing file_id and preserve caption entities."""
    caption_entities = list(source.caption_entities or [])
    kind = media_kind(source)

    common = dict(
        chat_id=chat_id,
        caption=source.caption,
        caption_entities=caption_entities or None,
        reply_markup=reply_markup,
        has_spoiler=bool(source.has_media_spoiler),
        show_caption_above_media=bool(source.show_caption_above_media),
    )

    if kind == "photo":
        return await bot.send_photo(
            photo=source.photo[-1].file_id,
            **common,
        )

    if kind == "video":
        return await bot.send_video(
            video=source.video.file_id,
            supports_streaming=True,
            **common,
        )

    raise RuntimeError("The source message does not contain supported media.")


async def send_preview(message: Message, bot: Bot) -> None:
    if message.media_group_id:
        await message.answer(
            "⚠️ Albums are deliberately blocked in this version so they cannot be "
            "published incorrectly as separate posts. Send one photo/video per post."
        )
        return

    await message.answer(
        "👀 <b>Preview</b>\n"
        "Nothing has been posted to the channel yet.",
        parse_mode="HTML",
    )

    await send_media(
        bot=bot,
        chat_id=message.chat.id,
        source=message,
        reply_markup=preview_keyboard(),
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    if not message.from_user:
        return
    await message.answer(
        f"Your Telegram user ID is: <code>{message.from_user.id}</code>",
        parse_mode="HTML",
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return

    await message.answer(
        "📣 <b>Channel Publisher is ready.</b>\n\n"
        "Send me one <b>photo or video</b> with its caption.\n"
        "I will create a private preview with:\n"
        "✅ Publish to channel\n"
        "✏️ Edit caption\n"
        "🗑 Cancel\n\n"
        "You can also send media without a caption and add it with "
        "<b>Edit caption</b> before publishing.\n\n"
        "Commands:\n"
        "/status — verify Render webhook + channel permission\n"
        "/myid — show your Telegram user ID",
        parse_mode="HTML",
    )


@router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return

    try:
        me = await bot.get_me()
        chat = await bot.get_chat(config.channel_id)
        member = await bot.get_chat_member(config.channel_id, me.id)
        webhook = await bot.get_webhook_info()

        can_post = getattr(member, "can_post_messages", None)
        if can_post is True:
            permission = "✅ Channel posting permission is enabled."
        elif can_post is False:
            permission = "❌ Bot lacks the channel Post Messages permission."
        else:
            permission = f"ℹ️ Channel membership status: {member.status}"

        expected = config.webhook_url
        webhook_ok = webhook.url.rstrip("/") == expected.rstrip("/")

        await message.answer(
            "🧪 <b>Render / Telegram status</b>\n\n"
            f"Bot: @{me.username or me.id}\n"
            f"Channel: {chat.title or chat.id}\n"
            f"{permission}\n\n"
            f"Webhook: {'✅' if webhook_ok else '❌'}\n"
            f"Pending Telegram updates: {webhook.pending_update_count}\n"
            f"Last webhook error: "
            f"{webhook.last_error_message or 'none'}",
            parse_mode="HTML",
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await message.answer(
            "❌ <b>Status check failed.</b>\n\n"
            "Check CHANNEL_ID and make sure this bot is an administrator of the "
            "channel with permission to post messages.\n\n"
            f"<code>{str(exc)}</code>",
            parse_mode="HTML",
        )


@router.message(F.photo | F.video)
async def receive_media(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return
    await send_preview(message, bot)


@router.callback_query(F.data == "edit_caption")
async def edit_caption(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return

    preview = callback.message
    if not preview or not media_kind(preview):
        await callback.answer("This preview is no longer valid.", show_alert=True)
        return

    await callback.answer()
    # The edit reference is embedded in the bot's ForceReply message itself.
    # No database/session state is needed, so Render restarts do not erase it.
    await preview.answer(
        "✏️ Reply to this message with the new caption.\n\n"
        f"<code>PUBLISHER_EDIT_REF:{preview.chat.id}:{preview.message_id}</code>",
        parse_mode="HTML",
        reply_markup=ForceReply(
            force_reply=True,
            input_field_placeholder="Type the new caption…",
            selective=True,
        ),
    )


@router.message(F.text)
async def receive_caption_edit(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return

    if message.text.startswith("/"):
        return

    replied = message.reply_to_message
    if not replied or not replied.from_user or not replied.from_user.is_bot:
        await message.answer(
            "Send a photo/video to create a post, or use the Edit caption button "
            "on an existing preview."
        )
        return

    match = EDIT_REF_RE.search(replied.text or "")
    if not match:
        await message.answer(
            "That reply is not linked to a publisher preview. "
            "Use the Edit caption button on the preview."
        )
        return

    chat_id = int(match.group(1))
    preview_message_id = int(match.group(2))

    if chat_id != message.chat.id:
        await message.answer("❌ Invalid edit reference.")
        return

    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=preview_message_id,
            caption=message.text,
            caption_entities=list(message.entities or []) or None,
            reply_markup=preview_keyboard(),
        )
    except TelegramBadRequest as exc:
        await message.answer(
            "❌ Telegram rejected that caption. It may be too long or contain "
            "unsupported formatting.\n\n"
            f"<code>{str(exc)}</code>\n\n"
            "Tap Edit caption on the preview and try again.",
            parse_mode="HTML",
        )
        return

    with suppress(TelegramBadRequest):
        await replied.delete()

    await message.answer("✅ Caption updated. Review the preview above.")


@router.callback_query(F.data == "cancel_preview")
async def cancel_preview(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return

    preview = callback.message
    if not preview:
        await callback.answer("Preview not found.", show_alert=True)
        return

    await callback.answer("Cancelled.")
    with suppress(TelegramBadRequest):
        await preview.delete()


@router.callback_query(F.data == "publish")
async def publish(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Not authorized.", show_alert=True)
        return

    preview = callback.message
    if not preview or not media_kind(preview):
        await callback.answer("This preview is no longer valid.", show_alert=True)
        return

    key = (preview.chat.id, preview.message_id)
    lock = _publish_locks[key]

    if lock.locked() or key in _published_in_process:
        await callback.answer("This post is already being processed.", show_alert=True)
        return

    async with lock:
        if key in _published_in_process:
            await callback.answer("This post was already processed.", show_alert=True)
            return

        _published_in_process.add(key)
        await callback.answer("Publishing…")

        # Remove active buttons immediately so accidental second taps are discouraged.
        with suppress(TelegramBadRequest):
            await preview.edit_reply_markup(reply_markup=None)

        try:
            sent = await send_media(
                bot=bot,
                chat_id=config.channel_id,
                source=preview,
                reply_markup=None,
            )
        except (TelegramBadRequest, TelegramForbiddenError) as exc:
            _published_in_process.discard(key)
            with suppress(TelegramBadRequest):
                await preview.edit_reply_markup(reply_markup=preview_keyboard())
            await preview.answer(
                "❌ <b>Publish failed.</b>\n"
                "The preview was kept. Check the channel ID and the bot's "
                "administrator permissions, then try again.\n\n"
                f"<code>{str(exc)}</code>",
                parse_mode="HTML",
            )
            return
        except Exception:
            log.exception("Unexpected publish failure for preview %s", key)
            _published_in_process.discard(key)
            with suppress(TelegramBadRequest):
                await preview.edit_reply_markup(reply_markup=preview_keyboard())
            await preview.answer(
                "❌ An unexpected error occurred. The preview was kept. "
                "Check the Render logs before retrying."
            )
            return

        await preview.answer(
            "✅ <b>Published successfully.</b>\n"
            f"Channel message ID: <code>{sent.message_id}</code>",
            parse_mode="HTML",
        )


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {
            "ok": True,
            "service": "telegram-channel-publisher",
            "mode": "webhook",
        }
    )


async def home(_: web.Request) -> web.Response:
    return web.Response(
        text=(
            "Telegram Channel Publisher is running.\n"
            "Use the Telegram bot to create and publish posts."
        ),
        content_type="text/plain",
    )


async def on_startup(app: web.Application) -> None:
    bot: Bot = app["bot"]

    # Webhook + secret-token verification.
    await bot.set_webhook(
        url=config.webhook_url,
        allowed_updates=dp.resolve_used_update_types(),
        secret_token=config.webhook_secret,
        drop_pending_updates=False,
    )

    me = await bot.get_me()
    log.info("Bot started: @%s (%s)", me.username, me.id)
    log.info("Webhook registered: %s", config.webhook_url)
    log.info("Target channel: %s", config.channel_id)


async def on_shutdown(app: web.Application) -> None:
    # Keep the webhook registered across normal Render restarts.
    log.info("Render service shutting down.")


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

    # Lets aiogram emit its own startup/shutdown lifecycle hooks.
    setup_application(app, dp, bot=bot)
    return app


if __name__ == "__main__":
    web.run_app(
        create_app(),
        host="0.0.0.0",
        port=config.port,
        access_log=log,
    )
