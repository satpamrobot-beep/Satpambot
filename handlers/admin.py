import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.context import FSMContext

from config import BOT_USERNAME, OWNER_ID

router = Router()

# =========================
# START COMMAND
# =========================
@router.message(F.text == "/start")
async def start(message: Message):

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add me to Group",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(
                text="📖 Help",
                callback_data="help"
            ),
            InlineKeyboardButton(
                text="📊 Stats",
                callback_data="stats"
            )
        ]
    ])

    if message.chat.type == "private":
        await message.answer(
            "🤖 <b>Group Manager Bot</b>\n\n"
            "📌 Bot ini membantu mengelola group kamu\n"
            "👮 Ban / Kick / Mute / Anti Spam\n\n"
            "➕ Tambahkan ke group dan jadikan admin\n",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message.answer("✅ Bot aktif di group ini")

# =========================
# HELP MENU (BUTTON)
# =========================
@router.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):

    text = (
        "📖 <b>HELP MENU</b>\n\n"
        "👮 Admin Commands:\n"
        "/ban (reply)\n"
        "/kick (reply)\n"
        "/mute (reply)\n"
        "/unmute (reply)\n\n"
        "⚠️ Bot hanya bekerja full di group\n"
        "🔒 Pastikan bot jadi admin"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

# =========================
# STATS SYSTEM (BASIC)
# =========================
@router.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery, bot):

    me = await bot.get_me()

    # basic stats (tanpa DB dulu)
    text = (
        "📊 <b>BOT STATISTICS</b>\n\n"
        f"🤖 Bot: @{me.username}\n"
        "👥 Mode: Group Manager\n"
        "⚡ Status: Online\n\n"
        "📌 Feature:\n"
        "- Moderation\n"
        "- Anti Spam\n"
        "- Auto Welcome\n"
    )

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

# =========================
# BROADCAST (OWNER ONLY)
# =========================
broadcast_users = set()  # nanti bisa diganti DB

@router.message(F.text.startswith("/broadcast"))
async def broadcast(message: Message, bot):

    if message.from_user.id != OWNER_ID:
        return await message.reply("❌ Only owner can use this")

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        return await message.reply("⚠️ Usage: /broadcast message")

    # dummy list (nanti pakai DB kalau upgrade)
    users = list(broadcast_users)

    sent = 0

    await message.reply("📢 Broadcasting...")

    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 Broadcast:\n\n{text}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            continue

    await message.reply(f"✅ Broadcast sent to {sent} users")

# =========================
# REGISTER USERS (optional tracking)
# =========================
@router.message()
async def register_users(message: Message):
    if message.chat.type == "private":
        broadcast_users.add(message.from_user.id)
