from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

router = Router()


# =========================
# LOCK MENU
# =========================

@router.callback_query(
    F.data == "open_locks"
)
async def locks_menu(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🔗 Links",
                    callback_data="lock_links"
                ),

                InlineKeyboardButton(
                    text="📷 Media",
                    callback_data="lock_media"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎭 Sticker",
                    callback_data="lock_sticker"
                ),

                InlineKeyboardButton(
                    text="🎥 Video",
                    callback_data="lock_video"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🖼 GIF",
                    callback_data="lock_gif"
                ),

                InlineKeyboardButton(
                    text="📎 Files",
                    callback_data="lock_files"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="panel_protect"
                )
            ]
        ]
    )

    await call.message.edit_text(
        """
🔒 Locks Menu

Pilih item yang ingin di lock / unlock.
""",
        reply_markup=keyboard
    )

    await call.answer()
