from aiogram import Router, F
from aiogram.types import Message
from database import db

router = Router()


# =========================
# NEW MEMBER HANDLER
# =========================
@router.message(F.new_chat_members)
async def new_member(message: Message):

    for user in message.new_chat_members:

        # ================= BOT JOIN =================
        if user.is_bot:

            await message.answer(
                "🤖 Bot berhasil ditambahkan!\n\n"
                "⚙️ Langkah setup:\n"
                "1. Jadikan admin\n"
                "2. Aktifkan izin delete & ban\n"
                "3. Ketik /help"
            )
            return

        # ================= GET WELCOME FROM DB =================
        row = await db.get_group(message.chat.id)

        text = (
            row["welcome"]
            if row and row["welcome"]
            else "👋 Welcome {user} to the group!"
        )

        await message.answer(
            text.replace("{user}", user.full_name)
        )


# =========================
# SET WELCOME
# =========================
@router.message(F.text.startswith("/setwelcome"))
async def setwelcome(message: Message):

    if not message.reply_to_message:
        return await message.reply(
            "❌ Reply pesan untuk dijadikan welcome"
        )

    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE groups
            SET welcome = $1
            WHERE chat_id = $2
            """,
            message.reply_to_message.text,
            message.chat.id
        )

    await message.reply("✅ Welcome message saved")
