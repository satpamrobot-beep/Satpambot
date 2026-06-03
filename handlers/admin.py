from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import BOT_USERNAME, OWNER_ID

router = Router()

# ================= START =================
@router.message(F.text == "/start")
async def start(message: Message):

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add to Group",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(text="📖 Help", callback_data="help"),
            InlineKeyboardButton(text="📊 Stats", callback_data="stats")
        ]
    ])

    if message.chat.type == "private":
        await message.answer(
            "🤖 <b>Group Manager Bot</b>\n\n"
            "📌 Cara pakai:\n"
            "1. Add bot ke group\n"
            "2. Jadikan admin\n"
            "3. Ketik /help di group\n\n"
            "⚠️ Bot hanya bekerja di group",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.answer("✅ Bot aktif di group ini")

# ================= HELP =================
@router.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):

    await callback.message.answer(
        "📖 <b>COMMAND LIST</b>\n\n"
        "👮 Moderation:\n"
        "/ban (reply)\n"
        "/kick (reply)\n"
        "/mute (reply)\n"
        "/unmute (reply)\n\n"
        "⚙️ Tools:\n"
        "/setwelcome (reply)\n"
        "/lock\n"
        "/filter <word>\n",
        parse_mode="HTML"
    )

    await callback.answer()

# ================= STATS =================
@router.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery, bot):

    me = await bot.get_me()

    await callback.message.answer(
        f"📊 BOT STATS\n\n"
        f"🤖 @{me.username}\n"
        f"⚡ Status: Online\n"
        f"👥 Mode: Group Manager\n"
    )

    await callback.answer()
