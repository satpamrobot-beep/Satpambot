from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text == "/start")
async def start(message: Message):
    if message.chat.type == "private":
        await message.answer(
            "🤖 Group Manager Bot\n\n"
            "➕ Add me to group\n"
            "👮 Make me admin\n\n"
            "📌 /help to see commands"
        )
    else:
        await message.answer("✅ Bot aktif di group ini")

@router.message(F.text == "/help")
async def help_cmd(message: Message):
    await message.answer(
        "📖 COMMAND LIST\n\n"
        "👮 Admin:\n"
        "/ban (reply)\n"
        "/kick (reply)\n"
        "/mute (reply)\n"
        "/unmute (reply)\n\n"
        "⚠️ Bot hanya bekerja full di group"
    )
