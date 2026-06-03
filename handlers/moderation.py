from aiogram import Router, F
from aiogram.types import Message, ChatPermissions
from aiogram.enums import ChatMemberStatus

from config import MAINTENANCE_MODE
from database import db

router = Router()

# =========================
# UX HELPERS
# =========================
def ok(t): return f"✅ {t}"
def warn(t): return f"⚠️ {t}"
def err(t): return f"❌ {t}"

# =========================
# MAINTENANCE GUARD
# =========================
async def maintenance_guard(message: Message):
    if MAINTENANCE_MODE:
        await message.reply("⚠️ Bot sedang maintenance")
        return True
    return False

# =========================
# ADMIN CHECK
# =========================
async def is_admin(message: Message):
    member = await message.bot.get_chat_member(
        message.chat.id,
        message.from_user.id
    )
    return member.status in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR
    ]

# =========================
# GET TARGET USER
# =========================
def get_target(message: Message):
    if not message.reply_to_message:
        return None
    return message.reply_to_message.from_user.id

# =========================
# BAN
# =========================
@router.message(F.text.startswith("/ban"))
async def ban(message: Message):

    if await maintenance_guard(message):
        return

    if not await is_admin(message):
        return await message.reply(err("Admin only"))

    user = get_target(message)
    if not user:
        return await message.reply(warn("Reply user untuk ban"))

    target = await message.bot.get_chat_member(message.chat.id, user)

    if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
        return await message.reply(err("Tidak bisa ban admin"))

    await message.bot.ban_chat_member(message.chat.id, user)

    await message.reply(ok("User banned"))
    await message.bot.send_message(message.chat.id, "🚫 User di-ban")

# =========================
# KICK
# =========================
@router.message(F.text.startswith("/kick"))
async def kick(message: Message):

    if await maintenance_guard(message):
        return

    if not await is_admin(message):
        return await message.reply(err("Admin only"))

    user = get_target(message)
    if not user:
        return await message.reply(warn("Reply user untuk kick"))

    target = await message.bot.get_chat_member(message.chat.id, user)

    if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
        return await message.reply(err("Tidak bisa kick admin"))

    await message.bot.ban_chat_member(message.chat.id, user)
    await message.bot.unban_chat_member(message.chat.id, user)

    await message.reply(ok("User kicked"))
    await message.bot.send_message(message.chat.id, "👢 User dikeluarkan")

# =========================
# MUTE
# =========================
@router.message(F.text.startswith("/mute"))
async def mute(message: Message):

    if await maintenance_guard(message):
        return

    if not await is_admin(message):
        return await message.reply(err("Admin only"))

    user = get_target(message)
    if not user:
        return await message.reply(warn("Reply user untuk mute"))

    target = await message.bot.get_chat_member(message.chat.id, user)

    if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
        return await message.reply(err("Tidak bisa mute admin"))

    await message.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=user,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_send_polls=False
        )
    )

    await message.reply(ok("User muted"))
    await message.bot.send_message(message.chat.id, "🔇 User tidak bisa chat")

# =========================
# UNMUTE
# =========================
@router.message(F.text.startswith("/unmute"))
async def unmute(message: Message):

    if await maintenance_guard(message):
        return

    if not await is_admin(message):
        return await message.reply(err("Admin only"))

    user = get_target(message)
    if not user:
        return await message.reply(warn("Reply user untuk unmute"))

    await message.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=user,
        permissions=ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True
        )
    )

    await message.reply(ok("User unmuted"))
    await message.bot.send_message(message.chat.id, "🔊 User bisa chat lagi")

# =========================
# WARN SYSTEM (SAFE + PERSISTENT)
# =========================
@router.message(F.text.startswith("/warn"))
async def warn_user(message: Message):

    if await maintenance_guard(message):
        return

    if not await is_admin(message):
        return await message.reply(err("Admin only"))

    user = get_target(message)
    if not user:
        return await message.reply(warn("Reply user untuk warn"))

    # add warn ke DB
    await db.add_warn(message.chat.id, user)

    data = await db.get_warn(message.chat.id, user)

    # FIX CRITICAL BUG
    count = data["count"] if data else 0

    await message.reply(f"⚠️ Warn {count}/3")

    # auto ban
    if count >= 3:
        await message.bot.ban_chat_member(message.chat.id, user)
        await db.reset_warn(message.chat.id, user)

        await message.reply("🚫 Auto banned (3 warn)")
        await message.bot.send_message(message.chat.id, "User diban karena 3 warning")
