from __future__ import annotations

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from common import config, database, deny, is_admin, TASHKENT
from keyboards import scheduled_list_keyboard
from time_utils import local_label

router = Router(name="general")


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    if not message.from_user:
        return
    await message.answer(
        f"Sizning Telegram ID'ingiz: <code>{message.from_user.id}</code>",
        parse_mode="HTML",
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return

    scheduler_line = (
        "✅ Rejalashtirish tizimi faol."
        if database
        else "⚠️ Rejalashtirish hali ma'lumotlar bazasiga ulanmagan."
    )

    await message.answer(
        "📣 <b>Kanal postlari boti tayyor.</b>\n\n"
        "Menga <b>rasm yoki video</b> yuboring. Matnni media bilan birga "
        "yozishingiz ham mumkin.\n\n"
        "Post avval sizga ko'rib chiqish uchun qaytadi. Keyin uni:\n"
        "✅ hozir kanalga joylashingiz,\n"
        "🗓 oldindan vaqtga qo'yishingiz,\n"
        "✏️ matnini tahrirlashingiz,\n"
        "🗑 yoki bekor qilishingiz mumkin.\n\n"
        f"{scheduler_line}\n\n"
        "<b>Buyruqlar:</b>\n"
        "/reja — rejalashtirilgan postlar\n"
        "/status — bot va kanal holati\n"
        "/myid — Telegram ID'ingiz",
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
            permission = "✅ Kanalga post joylash huquqi mavjud."
        elif can_post is False:
            permission = "❌ Botda kanalga post joylash huquqi yo'q."
        else:
            permission = f"ℹ️ Kanal holati: {member.status}"

        webhook_ok = webhook.url.rstrip("/") == config.webhook_url.rstrip("/")
        scheduler = "✅ Faol" if database else "⚠️ Ulanmagan"

        await message.answer(
            "🧪 <b>Bot holati</b>\n\n"
            f"Bot: @{me.username or me.id}\n"
            f"Kanal: {chat.title or chat.id}\n"
            f"{permission}\n\n"
            f"Webhook: {'✅' if webhook_ok else '❌'}\n"
            f"Rejalashtirish: {scheduler}\n"
            f"Telegram navbatidagi yangilanishlar: {webhook.pending_update_count}\n"
            f"Oxirgi webhook xatosi: {webhook.last_error_message or 'yo‘q'}",
            parse_mode="HTML",
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await message.answer(
            "❌ <b>Tekshiruv muvaffaqiyatsiz.</b>\n\n"
            "CHANNEL_ID ni va botning kanaldagi administrator huquqlarini tekshiring.\n\n"
            f"<code>{str(exc)}</code>",
            parse_mode="HTML",
        )


@router.message(Command("reja"))
async def cmd_schedule_list(message: Message) -> None:
    if not is_admin(message.from_user.id if message.from_user else None):
        await deny(message)
        return

    if not database:
        await message.answer(
            "⚠️ Rejalashtirish tizimi hali PostgreSQL bazasiga ulanmagan."
        )
        return

    posts = await database.list_scheduled(user_id=message.from_user.id, limit=20)
    if not posts:
        await message.answer("📭 Hozircha rejalashtirilgan postlar yo'q.")
        return

    lines = ["🗓 <b>Yaqin rejalashtirilgan postlar</b>\n"]
    buttons: list[tuple[int, str]] = []

    for post in posts:
        label = local_label(post.scheduled_at)
        snippet = (post.caption or "(matnsiz)").replace("\n", " ")
        if len(snippet) > 42:
            snippet = snippet[:39] + "..."
        lines.append(f"• <b>#{post.id}</b> — {label}\n  {snippet}")
        buttons.append(
            (
                post.id,
                post.scheduled_at.astimezone(TASHKENT).strftime("%d.%m %H:%M"),
            )
        )

    lines.append("\nPastdagi tugma orqali kerakli postni bekor qilishingiz mumkin.")
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=scheduled_list_keyboard(buttons),
    )
