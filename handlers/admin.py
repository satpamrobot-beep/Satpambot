from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus

router = Router()

async def is_admin(message: Message):
    member = await message.bot.get_chat_member(
        message.chat.id,
        message.from_user.id
    )
    return member.status in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]

@router.message(F.text == "/start")
async def start_cmd(message: Message):
    await message.answer("🤖 Bot aktif dan siap digunakan!")

@router.message(F.text == "/id")
async def get_id(message: Message):
    await message.answer(f"🆔 ID kamu: {message.from_user.id}")
