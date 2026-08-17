from __future__ import annotations

from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, ForceReply

from common import config, is_admin
from keyboards import direct_keyboard
from media import media_kind, send_direct_media_from_message

router = Router(name="direct")


@router.callback_query(F.data == "edit_direct")
async def edit_direct(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    preview = callback.message
    if not preview or not media_kind(preview):
        await callback.answer("Ko'rib chiqish xabari topilmadi.", show_alert=True)
        return

    await callback.answer()
    await preview.answer(
        "✏️ Yangi matnni shu xabarga <b>Reply</b> qilib yuboring.\n\n"
        f"<code>PUBLISHER_DIRECT_EDIT_REF:{preview.chat.id}:{preview.message_id}</code>",
        parse_mode="HTML",
        reply_markup=ForceReply(
            force_reply=True,
            input_field_placeholder="Yangi post matni...",
            selective=True,
        ),
    )


@router.callback_query(F.data == "cancel_direct")
async def cancel_direct(callback: CallbackQuery) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    await callback.answer("Bekor qilindi.")
    if callback.message:
        with suppress(TelegramBadRequest):
            await callback.message.delete()


@router.callback_query(F.data == "publish_direct")
async def publish_direct(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    preview = callback.message
    if not preview or not media_kind(preview):
        await callback.answer("Ko'rib chiqish xabari topilmadi.", show_alert=True)
        return

    await callback.answer("Joylanmoqda…")
    with suppress(TelegramBadRequest):
        await preview.edit_reply_markup(reply_markup=None)

    try:
        sent = await send_direct_media_from_message(
            bot=bot,
            chat_id=config.channel_id,
            source=preview,
            reply_markup=None,
        )
    except Exception as exc:
        with suppress(TelegramBadRequest):
            await preview.edit_reply_markup(reply_markup=direct_keyboard())
        await preview.answer(
            "❌ Post joylanmadi. Qayta urinishingiz mumkin.\n\n"
            f"<code>{str(exc)}</code>",
            parse_mode="HTML",
        )
        return

    await preview.answer(
        "✅ <b>Post kanalga joylandi.</b>\n"
        f"Kanal xabar ID: <code>{sent.message_id}</code>",
        parse_mode="HTML",
    )
