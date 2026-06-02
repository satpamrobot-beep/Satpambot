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

# =====================
# BAN USER
# =====================
@router.message(F.text.startswith("/ban"))
async def ban_user(message: Message):
    if not await is_admin(message):
        return await message.reply("❌ Kamu bukan admin")

    if not message.reply_to_message:
        return await message.reply("⚠️ Reply user untuk ban")

    user_id = message.reply_to_message.from_user.id
    await message.bot.ban_chat_member(message.chat.id, user_id)

    await message.reply("✅ User berhasil diban")

# =====================
# UNBAN USER
# =====================
@router.message(F.text.startswith("/unban"))
async def unban_user(message: Message):
    if not await is_admin(message):
        return await message.reply("❌ Kamu bukan admin")

    try:
        user_id = int(message.text.split()[1])
    except:
        return await message.reply("⚠️ Gunakan /unban <user_id>")

    await message.bot.unban_chat_member(message.chat.id, user_id)

    await message.reply("✅ User berhasil di-unban")

# =====================
# KICK USER
# =====================
@router.message(F.text.startswith("/kick"))
async def kick_user(message: Message):
    if not await is_admin(message):
        return await message.reply("❌ Kamu bukan admin")

    if not message.reply_to_message:
        return await message.reply("⚠️ Reply user untuk kick")

    user_id = message.reply_to_message.from_user.id

    await message.bot.ban_chat_member(message.chat.id, user_id)
    await message.bot.unban_chat_member(message.chat.id, user_id)

    await message.reply("👢 User di-kick")
