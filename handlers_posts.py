from __future__ import annotations

from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ForceReply, Message

from common import MAX_SCHEDULE_DAYS, config, database, deny, is_admin
from keyboards import direct_keyboard, draft_keyboard
from media import send_direct_media_from_message, send_post_media

router = Router(name="posts")


@router.message(F.photo | F.video)
async def receive_media(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return

    if message.media_group_id:
        await message.answer(
            "⚠️ Hozircha albom rejimi yoqilmagan. "
            "Iltimos, har bir post uchun bitta rasm yoki bitta video yuboring."
        )
        return

    if not database:
        await message.answer(
            "👀 <b>Ko'rib chiqish</b>\n"
            "Rejalashtirish bazasi hali ulanmagan. "
            "Hozirgi postni darhol joylash mumkin.",
            parse_mode="HTML",
        )
        await send_direct_media_from_message(
            bot=bot,
            chat_id=message.chat.id,
            source=message,
            reply_markup=direct_keyboard(),
        )
        return

    media_type = "photo" if message.photo else "video"
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id

    post_id = await database.create_post(
        user_id=message.from_user.id,
        media_type=media_type,
        file_id=file_id,
        caption=message.caption,
        entities=list(message.caption_entities or []),
        has_spoiler=bool(message.has_media_spoiler),
        show_caption_above_media=bool(message.show_caption_above_media),
    )
    post = await database.get_post(post_id)

    await message.answer(
        f"👀 <b>Ko'rib chiqish — Post #{post_id}</b>\n"
        "Hali kanalga joylanmadi.",
        parse_mode="HTML",
    )
    await send_post_media(
        bot=bot,
        chat_id=message.chat.id,
        post=post,
        reply_markup=draft_keyboard(post_id, scheduler_enabled=True),
    )


@router.callback_query(F.data.startswith("edit:"))
async def edit_caption(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    if not database:
        await callback.answer("Scheduler bazasi ulanmagan.", show_alert=True)
        return

    post_id = int(callback.data.split(":", 1)[1])
    post = await database.get_post(post_id)
    if not post or post.user_id != callback.from_user.id or post.status != "draft":
        await callback.answer("Bu postni tahrirlab bo'lmaydi.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "✏️ Yangi matnni shu xabarga <b>Reply</b> qilib yuboring.\n\n"
        f"<code>PUBLISHER_EDIT_REF:{post_id}</code>",
        parse_mode="HTML",
        reply_markup=ForceReply(
            force_reply=True,
            input_field_placeholder="Yangi post matni...",
            selective=True,
        ),
    )


@router.callback_query(F.data.startswith("schedule:"))
async def ask_schedule_time(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    if not database:
        await callback.answer("Rejalashtirish bazasi ulanmagan.", show_alert=True)
        return

    post_id = int(callback.data.split(":", 1)[1])
    post = await database.get_post(post_id)
    if not post or post.user_id != callback.from_user.id or post.status != "draft":
        await callback.answer("Bu postni rejalashtirib bo'lmaydi.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(
        "🗓 <b>Post qachon chiqsin?</b>\n\n"
        "Toshkent vaqti bilan quyidagi formatda yozing:\n"
        "<code>25.08.2026 18:30</code>\n\n"
        "Yoki joriy yil uchun qisqaroq:\n"
        "<code>25.08 18:30</code>\n\n"
        f"Eng ko'pi bilan {MAX_SCHEDULE_DAYS} kun oldindan rejalashtirish mumkin.\n\n"
        f"<code>PUBLISHER_SCHEDULE_REF:{post_id}</code>",
        parse_mode="HTML",
        reply_markup=ForceReply(
            force_reply=True,
            input_field_placeholder="25.08.2026 18:30",
            selective=True,
        ),
    )


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_draft(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    if not database:
        await callback.answer("Baza ulanmagan.", show_alert=True)
        return

    post_id = int(callback.data.split(":", 1)[1])
    ok = await database.cancel_post(post_id=post_id, user_id=callback.from_user.id)
    if not ok:
        await callback.answer("Bu postni bekor qilib bo'lmaydi.", show_alert=True)
        return

    await callback.answer("Bekor qilindi.")
    with suppress(TelegramBadRequest):
        await callback.message.delete()


@router.callback_query(F.data.startswith("cancel_scheduled:"))
async def cancel_scheduled(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    if not database:
        await callback.answer("Baza ulanmagan.", show_alert=True)
        return

    post_id = int(callback.data.split(":", 1)[1])
    ok = await database.cancel_post(post_id=post_id, user_id=callback.from_user.id)
    if not ok:
        await callback.answer(
            "Post allaqachon joylangan yoki bekor qilingan.",
            show_alert=True,
        )
        return

    await callback.answer(f"Post #{post_id} bekor qilindi.", show_alert=True)
    if callback.message:
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(F.data.startswith("publish:"))
async def publish_now(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return
    if not database:
        await callback.answer("Baza ulanmagan.", show_alert=True)
        return

    post_id = int(callback.data.split(":", 1)[1])
    claimed = await database.claim_immediate(
        post_id=post_id,
        user_id=callback.from_user.id,
    )
    if not claimed:
        await callback.answer("Bu post allaqachon qayta ishlangan.", show_alert=True)
        return

    await callback.answer("Joylanmoqda…")
    post = await database.get_post(post_id)

    try:
        sent = await send_post_media(
            bot=bot,
            chat_id=config.channel_id,
            post=post,
            reply_markup=None,
        )
    except Exception as exc:
        await database.release_immediate(
            post_id=post_id,
            user_id=callback.from_user.id,
            error=str(exc),
        )
        await callback.message.answer(
            "❌ Post joylanmadi. Post saqlab qolindi, qayta urinishingiz mumkin.\n\n"
            f"<code>{str(exc)}</code>",
            parse_mode="HTML",
        )
        return

    await database.mark_published(post_id=post_id, message_id=sent.message_id)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer(
        "✅ <b>Post kanalga joylandi.</b>\n"
        f"Post #{post_id} · Kanal xabar ID: <code>{sent.message_id}</code>",
        parse_mode="HTML",
    )
