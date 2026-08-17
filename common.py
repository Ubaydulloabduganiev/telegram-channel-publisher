from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

from aiogram.types import Message

from config import Config, load_config
from db import Database

config: Config = load_config()
database: Database | None = Database(config.database_url) if config.database_url else None

TASHKENT = ZoneInfo("Asia/Tashkent")
UTC = timezone.utc
MAX_SCHEDULE_DAYS = 31


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in config.admin_ids


async def deny(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    await message.answer(
        "⛔ Sizga bu botdan foydalanishga ruxsat berilmagan.\n"
        f"Sizning Telegram ID'ingiz: <code>{user_id}</code>",
        parse_mode="HTML",
    )
