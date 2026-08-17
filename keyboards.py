from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Publish to channel",
                    callback_data="publish",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Edit caption",
                    callback_data="edit_caption",
                ),
                InlineKeyboardButton(
                    text="🗑 Cancel",
                    callback_data="cancel_preview",
                ),
            ],
        ]
    )
