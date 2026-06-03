from aiogram import Router, F
from aiogram.types import Message

router = Router()

welcome_text = {}

# =========================
# NEW MEMBER HANDLER (SINGLE ENTRY)
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

        # ================= USER JOIN =================
        text = welcome_text.get(
            message.chat.id,
            "👋 Welcome {user} to the group!"
        )

        await message.answer(text.replace("{user}", user.full_name))

# =========================
# SET WELCOME
# =========================
@router.message(F.text.startswith("/setwelcome"))
async def setwelcome(message: Message):

    if not message.reply_to_message:
        return await message.reply("❌ Reply pesan untuk dijadikan welcome")

    welcome_text[message.chat.id] = message.reply_to_message.text

    await message.reply("✅ Welcome message saved")
