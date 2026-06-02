import asyncio
import re
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.enums import ChatMemberStatus
from collections import defaultdict

TOKEN = "ISI_TOKEN_BOT"

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# =========================
# SIMPLE MEMORY (GANTI DB NANTI)
# =========================
warns = defaultdict(int)
flood = defaultdict(list)

# =========================
# ANTI LINK
# =========================
LINK_REGEX = re.compile(r"(https?://|t\.me/|www\.)")

def is_admin(chat_member):
    return chat_member.status in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]

# =========================
# WELCOME
# =========================
@router.message(F.new_chat_members)
async def welcome(message: Message):
    for user in message.new_chat_members:
        await message.answer(
            f"👋 Welcome {user.full_name} di grup!"
        )

# =========================
# ANTI LINK + WARN SYSTEM
# =========================
@router.message()
async def moderation(message: Message):
    if not message.text:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    # cek admin
    member = await bot.get_chat_member(chat_id, user_id)
    if is_admin(member):
        return

    text = message.text.lower()

    # anti link
    if LINK_REGEX.search(text):
        await message.delete()

        warns[user_id] += 1

        await message.answer(
            f"⚠️ Jangan kirim link!\nWarn: {warns[user_id]}/3"
        )

        # auto ban
        if warns[user_id] >= 3:
            await bot.ban_chat_member(chat_id, user_id)
            await message.answer("🚫 User diban karena spam link")
        return

# =========================
# COMMAND BAN
# =========================
@router.message(F.text.startswith("/ban"))
async def ban(message: Message):
    if not message.reply_to_message:
        return

    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id

    member = await bot.get_chat_member(chat_id, message.from_user.id)
    if not is_admin(member):
        return

    await bot.ban_chat_member(chat_id, user_id)
    await message.answer("🚫 User diban")

# =========================
# COMMAND MUTE
# =========================
@router.message(F.text.startswith("/mute"))
async def mute(message: Message):
    if not message.reply_to_message:
        return

    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id

    member = await bot.get_chat_member(chat_id, message.from_user.id)
    if not is_admin(member):
        return

    await bot.restrict_chat_member(
        chat_id,
        user_id,
        permissions={}
    )

    await message.answer("🔇 User dimute")

# =========================
# START BOT
# =========================
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
