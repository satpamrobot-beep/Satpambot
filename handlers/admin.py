from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text == "/start")
async def start(message: Message):
    await message.answer("🤖 Tzy Security Bot aktif!")
