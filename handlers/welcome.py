from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.new_chat_members)
async def welcome(message: Message):
    for user in message.new_chat_members:
        await message.answer(
            f"👋 Welcome {user.full_name}\n\n"
            "📌 Selamat datang di group!\n"
            "⚠️ Jangan spam / toxic"
        )
