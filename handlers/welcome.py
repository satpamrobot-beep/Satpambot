from aiogram import Router, F
from aiogram.types import Message

router = Router()

welcome_text = {}

# ================= BOT JOIN =================
@router.message(F.new_chat_members)
async def on_join(message: Message):

    for user in message.new_chat_members:

        if user.is_bot:
            await message.answer(
                "🤖 Bot berhasil ditambahkan!\n\n"
                "⚙️ Langkah:\n"
                "1. Jadikan admin\n"
                "2. Beri izin delete & ban\n"
                "3. Ketik /help",
            )

# ================= WELCOME USER =================
@router.message(F.new_chat_members)
async def greet(message: Message):

    text = "👋 Welcome {user}"

    for user in message.new_chat_members:
        if not user.is_bot:
            await message.answer(text.replace("{user}", user.full_name))

# ================= SET WELCOME =================
@router.message(F.text.startswith("/setwelcome"))
async def setwelcome(message: Message):

    if not message.reply_to_message:
        return await message.reply("Reply pesan")

    welcome_text[message.chat.id] = message.reply_to_message.text
    await message.reply("✅ Welcome disimpan")

# ================= AUTO GREET =================
@router.message(F.new_chat_members)
async def auto_greet(message: Message):

    for user in message.new_chat_members:
        if user.is_bot:
            return

        text = welcome_text.get(message.chat.id, "👋 Welcome {user}")

        await message.answer(text.replace("{user}", user.full_name))
