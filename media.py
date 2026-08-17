from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message

from db import Post


def media_kind(message: Message) -> str | None:
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    return None


async def send_post_media(*, bot: Bot, chat_id: int | str, post: Post, reply_markup=None) -> Message:
    common = dict(
        chat_id=chat_id,
        caption=post.caption,
        caption_entities=post.entities,
        reply_markup=reply_markup,
        has_spoiler=post.has_spoiler,
        show_caption_above_media=post.show_caption_above_media,
    )
    if post.media_type == "photo":
        return await bot.send_photo(photo=post.file_id, **common)
    if post.media_type == "video":
        return await bot.send_video(video=post.file_id, supports_streaming=True, **common)
    raise RuntimeError(f"Noma'lum media turi: {post.media_type}")


async def send_direct_media_from_message(*, bot: Bot, chat_id: int | str, source: Message, reply_markup=None) -> Message:
    common = dict(
        chat_id=chat_id,
        caption=source.caption,
        caption_entities=list(source.caption_entities or []) or None,
        reply_markup=reply_markup,
        has_spoiler=bool(source.has_media_spoiler),
        show_caption_above_media=bool(source.show_caption_above_media),
    )
    if source.photo:
        return await bot.send_photo(photo=source.photo[-1].file_id, **common)
    if source.video:
        return await bot.send_video(video=source.video.file_id, supports_streaming=True, **common)
    raise RuntimeError("Media topilmadi.")
