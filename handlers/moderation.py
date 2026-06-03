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

# ================= BAN =================
@router.message(F.text.startswith("/ban"))
async def ban(message: Message):
    if not await is_admin(message):
        return await message.reply("❌ Bukan admin")

    if not message.reply_to_message:
        return await message.reply("Reply user untuk ban")

    user = message.reply_to_message.from_user.id
    await message.bot.ban_chat_member(message.chat.id, user)
    await message.reply("✅ User diban")

# ================= KICK =================
@router.message(F.text.startswith("/kick"))
async def kick(message: Message):
    if not await is_admin(message):
        return

    if not message.reply_to_message:
        return

    user = message.reply_to_message.from_user.id
    await message.bot.ban_chat_member(message.chat.id, user)
    await message.bot.unban_chat_member(message.chat.id, user)

    await message.reply("👢 User di-kick")

# ================= MUTE (simple) =================
@router.message(F.text.startswith("/mute"))
async def mute(message: Message):
    if not await is_admin(message):
        return

    if not message.reply_to_message:
        return

    user = message.reply_to_message.from_user.id

    await message.bot.restrict_chat_member(
        message.chat.id,
        user,
        permissions={
            "can_send_messages": False
        }
    )

    await message.reply("🔇 User dimute")

# ================= UNMUTE =================
@router.message(F.text.startswith("/unmute"))
async def unmute(message: Message):
    if not await is_admin(message):
        return

    if not message.reply_to_message:
        return

    user = message.reply_to_message.from_user.id

    await message.bot.restrict_chat_member(
        message.chat.id,
        user,
        permissions={
            "can_send_messages": True
        }
    )

    await message.reply("🔊 User di-unmute")
