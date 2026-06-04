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

            # simpan group ke DB
            await db.add_group(
                chat_id=chat.id,
                title=chat.title,
                owner_id=message.from_user.id
            )

            await message.reply(
"""
👋 Terima kasih sudah menambahkan bot!

⚠ STEP PENTING:
👉 Jadikan bot ADMIN agar semua fitur aktif

📌 Setelah itu panel akan terbuka otomatis
"""
            )


# =========================
# DETEKSI STATUS BOT DI GROUP
# =========================
@router.chat_member()
async def bot_status_update(event: ChatMemberUpdated):

    bot_id = (await event.bot.get_me()).id

    # hanya proses kalau perubahan untuk bot sendiri
    if event.new_chat_member.user.id != bot_id:
        return

    chat = event.chat
    status = event.new_chat_member.status

    # =========================
    # BOT JADI ADMIN / CREATOR
    # =========================
    if status in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]:

        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE groups
                SET is_admin = TRUE
                WHERE chat_id = $1
                """,
                chat.id
            )

        await event.bot.send_message(
            chat.id,
"""
✅ BOT SUDAH ADMIN

⚙ Panel sekarang AKTIF
Ketik /panel atau tekan tombol panel
"""
        )


    # =========================
    # BOT DITURUNKAN / DIKELUARKAN
    # =========================
    elif status == ChatMemberStatus.MEMBER:

        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE groups
                SET is_admin = FALSE
                WHERE chat_id = $1
                """,
                chat.id
            )

        await event.bot.send_message(
            chat.id,
"""
⚠ BOT TIDAK LAGI ADMIN

❌ Panel terkunci
👉 Jadikan bot admin lagi untuk mengaktifkan fitur
"""
        )


# =========================
# OPTIONAL: BOT LEFT GROUP
# =========================
@router.message(F.left_chat_member)
async def bot_left_group(message: Message):

    bot_id = (await message.bot.get_me()).id

    if message.left_chat_member.id == bot_id:

        await message.reply(
"""
👋 Bot telah dikeluarkan dari group

📌 Kita tetap stay jika kamu butuh lagi😚
"""
        )
