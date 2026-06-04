from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.enums import ChatMemberStatus

from database import db

router = Router()


# =========================
# BOT JOIN GROUP
# =========================
@router.message(F.new_chat_members)
async def bot_added_to_group(message: Message):

    bot_id = (await message.bot.get_me()).id

    for member in message.new_chat_members:

        if member.id == bot_id:

            chat = message.chat

            await db.add_group(
                chat.id,
                chat.title,
                message.from_user.id
            )

            await message.reply(
                "👋 Terima kasih sudah menambahkan bot!\n\n"
                "⚠ Jadikan bot ADMIN agar semua fitur aktif"
            )


# =========================
# BOT STATUS CHANGE
# =========================
@router.chat_member()
async def bot_status_update(event: ChatMemberUpdated):

    bot_id = (await event.bot.get_me()).id

    if event.new_chat_member.user.id != bot_id:
        return

    chat_id = event.chat.id
    status = event.new_chat_member.status

    # BOT JADI ADMIN
    if status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:

        await event.bot.send_message(
            chat_id,
            "✅ Bot sudah ADMIN\n⚙ Panel aktif sekarang"
        )

    # BOT BUKAN ADMIN / MEMBER
    elif status == ChatMemberStatus.MEMBER:

        await event.bot.send_message(
            chat_id,
            "⚠ Bot bukan admin\n❌ Fitur nonaktif"
        )


# =========================
# BOT LEFT GROUP
# =========================
@router.message(F.left_chat_member)
async def bot_left_group(message: Message):

    bot_id = (await message.bot.get_me()).id

    if message.left_chat_member.id == bot_id:

        await message.reply(
            "👋 Bot telah dikeluarkan dari group\n\n"
            "💔 Jika butuh, tinggal add lagi ya"
        )
