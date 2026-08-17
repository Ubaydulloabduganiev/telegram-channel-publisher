from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def draft_keyboard(post_id: int, scheduler_enabled: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✅ Hozir joylash",
                callback_data=f"publish:{post_id}",
            )
        ]
    ]
    if scheduler_enabled:
        rows.append(
            [
                InlineKeyboardButton(
                    text="🗓 Vaqtga rejalashtirish",
                    callback_data=f"schedule:{post_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="✏️ Matnni tahrirlash",
                callback_data=f"edit:{post_id}",
            ),
            InlineKeyboardButton(
                text="🗑 Bekor qilish",
                callback_data=f"cancel:{post_id}",
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def scheduled_list_keyboard(items: list[tuple[int, str]]) -> InlineKeyboardMarkup | None:
    if not items:
        return None
    rows = []
    for post_id, time_label in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 #{post_id} · {time_label}",
                    callback_data=f"cancel_scheduled:{post_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def direct_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Hozir joylash",
                    callback_data="publish_direct",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Matnni tahrirlash",
                    callback_data="edit_direct",
                ),
                InlineKeyboardButton(
                    text="🗑 Bekor qilish",
                    callback_data="cancel_direct",
                ),
            ],
        ]
    )
