from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart

from database import db

router = Router()


# =========================
# START PRIVATE
# =========================

@router.message(
    CommandStart(),
    F.chat.type == "private"
)
async def start_private(
    message: Message
):

    user = message.from_user

    await db.add_user(
        user.id
    )

    users = await db.count_users()
    groups = await db.count_groups()

    bot_info = await message.bot.get_me()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="➕ Add Me To Group",
                    url=f"https://t.me/{bot_info.username}?startgroup=true"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📚 Help",
                    callback_data="help_menu"
                ),

                InlineKeyboardButton(
                    text="📊 Stats",
                    callback_data="bot_stats"
                )
            ],

            [
                InlineKeyboardButton(
                    text="❤️ Support",
                    url="https://t.me/yourchannel"
                )
            ]
        ]
    )

    text = f"""
👋 Halo {user.first_name}

Saya adalah bot moderator grup.

⚡ Features:

• Warn System
• Mute / Ban
• Filters
• Notes
• Anti Spam
• Reports
• Captcha
• Join Request

📊 Bot Stats:

Users: {users}
Groups: {groups}

Tambahkan saya ke grup untuk memulai.
"""

    await message.answer(
        text,
        reply_markup=keyboard
    )


# =========================
# BOT MASUK GROUP
# =========================

@router.message(
    F.new_chat_members
)
async def bot_added(
    message: Message
):

    me = await message.bot.get_me()

    for member in message.new_chat_members:

        if member.id != me.id:
            continue

        owner = (
            message.from_user.id
            if message.from_user
            else 0
        )

        await db.add_group(
            message.chat.id,
            message.chat.title,
            owner
        )

        await message.answer(
            "✅ Bot moderator aktif.\nGunakan /help untuk command."
        )


# =========================
# BOT KELUAR GROUP
# =========================

@router.message(
    F.left_chat_member
)
async def bot_left(
    message: Message
):

    if not message.left_chat_member:
        return

    me = await message.bot.get_me()

    if message.left_chat_member.id != me.id:
        return

    print(
        f"Left group: {message.chat.id}"
    )
