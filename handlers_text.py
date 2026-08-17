from __future__ import annotations

import re
from contextlib import suppress

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from common import MAX_SCHEDULE_DAYS, database, deny, is_admin
from keyboards import direct_keyboard, draft_keyboard
from media import send_post_media
from time_utils import local_label, parse_schedule_time

router = Router(name="text")

EDIT_REF_RE = re.compile(r"PUBLISHER_EDIT_REF:(\d+)")
SCHEDULE_REF_RE = re.compile(r"PUBLISHER_SCHEDULE_REF:(\d+)")
DIRECT_EDIT_REF_RE = re.compile(r"PUBLISHER_DIRECT_EDIT_REF:(-?\d+):(\d+)")


@router.message(F.text)
async def receive_reply_text(message: Message, bot: Bot) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return
    if message.text.startswith("/"):
        return

    replied = message.reply_to_message
    if not replied or not replied.from_user or not replied.from_user.is_bot:
        await message.answer(
            "Post yaratish uchun rasm/video yuboring yoki mavjud post tugmalaridan foydalaning."
        )
        return

    text = replied.text or ""

    direct_edit = DIRECT_EDIT_REF_RE.search(text)
    if direct_edit:
        chat_id = int(direct_edit.group(1))
        preview_message_id = int(direct_edit.group(2))

        if chat_id != message.chat.id:
            await message.answer("❌ Tahrirlash havolasi noto'g'ri.")
            return

        try:
            await bot.edit_message_caption(
                chat_id=chat_id,
                message_id=preview_message_id,
                caption=message.text,
                caption_entities=list(message.entities or []) or None,
                reply_markup=direct_keyboard(),
            )
        except TelegramBadRequest as exc:
            await message.answer(
                "❌ Telegram bu matnni qabul qilmadi. Matn juda uzun yoki "
                "formatda muammo bo'lishi mumkin.\n\n"
                f"<code>{str(exc)}</code>",
                parse_mode="HTML",
            )
            return

        with suppress(TelegramBadRequest):
            await replied.delete()
        await message.answer("✅ Matn yangilandi.")
        return

    if not database:
        await message.answer("⚠️ Rejalashtirish bazasi ulanmagan.")
        return

    edit_match = EDIT_REF_RE.search(text)
    if edit_match:
        post_id = int(edit_match.group(1))
        post = await database.get_post(post_id)

        if not post or post.user_id != message.from_user.id or post.status != "draft":
            await message.answer("❌ Bu post endi tahrirlab bo'lmaydi.")
            return

        updated = await database.update_caption(
            post_id=post_id,
            user_id=message.from_user.id,
            caption=message.text,
            entities=list(message.entities or []),
        )
        if not updated:
            await message.answer("❌ Matnni yangilab bo'lmadi.")
            return

        updated_post = await database.get_post(post_id)
        with suppress(TelegramBadRequest):
            await replied.delete()

        await message.answer("✅ Matn yangilandi. Yangi ko'rib chiqish nusxasi:")
        await send_post_media(
            bot=bot,
            chat_id=message.chat.id,
            post=updated_post,
            reply_markup=draft_keyboard(post_id, scheduler_enabled=True),
        )
        return

    schedule_match = SCHEDULE_REF_RE.search(text)
    if schedule_match:
        post_id = int(schedule_match.group(1))
        post = await database.get_post(post_id)

        if not post or post.user_id != message.from_user.id or post.status != "draft":
            await message.answer("❌ Bu post endi rejalashtirib bo'lmaydi.")
            return

        try:
            scheduled_utc = parse_schedule_time(message.text)
        except ValueError as exc:
            reason = str(exc)
            if reason == "past":
                explanation = "Bu vaqt o'tib ketgan."
            elif reason == "too_far":
                explanation = (
                    f"Faqat {MAX_SCHEDULE_DAYS} kun oldindan rejalashtirish mumkin."
                )
            else:
                explanation = "Sana yoki vaqt formati noto'g'ri."

            await message.answer(
                f"❌ {explanation}\n\n"
                "Masalan:\n"
                "<code>25.08.2026 18:30</code>\n"
                "yoki <code>25.08 18:30</code>\n\n"
                "Rejalashtirish tugmasini yana bosing.",
                parse_mode="HTML",
            )
            return

        ok = await database.schedule_post(
            post_id=post_id,
            user_id=message.from_user.id,
            scheduled_at=scheduled_utc,
        )
        if not ok:
            await message.answer("❌ Post holati o'zgargan. Qayta urinib ko'ring.")
            return

        with suppress(TelegramBadRequest):
            await replied.delete()

        await message.answer(
            "✅ <b>Post rejalashtirildi.</b>\n\n"
            f"Post: <b>#{post_id}</b>\n"
            f"Vaqt: <b>{local_label(scheduled_utc)}</b> (Toshkent)\n\n"
            "Bot shu vaqtda postni kanalga avtomatik joylaydi.\n"
            "/reja orqali barcha navbatdagi postlarni ko'rishingiz mumkin.",
            parse_mode="HTML",
        )
        return

    await message.answer(
        "Bu Reply post tahriri yoki rejalashtirish so'roviga tegishli emas."
    )
