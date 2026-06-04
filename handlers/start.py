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

    try:
        await db.add_user(user.id)
        users = await db.count_users()
        groups = await db.count_groups()
    except Exception as e:
        print(f"Database Error: {e}")
        users = 0
        groups = 0

    bot_username = message.bot.username

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Tambahkan ke Grup",
                    url=f"https://t.me/{bot_username}?startgroup=true"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Bantuan",
                    callback_data="help_menu"
                ),
                InlineKeyboardButton(
                    text="📊 Statistik",
                    callback_data="bot_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❤️ Dukungan",
                    url="https://t.me/yourchannel"
                )
            ]
        ]
    )

    text = (
        f"👋 Halo {user.first_name}!\n\n"
        f"Saya adalah bot moderator grup.\n\n"
        f"👤 Pengguna: {users}\n"
        f"👥 Grup: {groups}"
    )

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

        bot_member = await message.bot.get_chat_member(
            message.chat.id,
            me.id
        )

        if bot_member.status != "administrator":

            await message.answer(
                "👋 Terima kasih telah menambahkan saya.\n\n"
                "⚠️ Jadikan saya Admin terlebih dahulu agar semua fitur moderasi dapat digunakan."
            )

        else:

            await message.answer(
                "✅ Bot berhasil diaktifkan.\n\n"
                "Saya sudah memiliki hak Admin dan siap membantu mengelola grup.\n\n"
                "Gunakan /help untuk melihat daftar perintah."
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
