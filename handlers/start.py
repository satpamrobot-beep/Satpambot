from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_USERNAME

router = Router()

# =========================
# /START HANDLER (PRIVATE ONLY UX)
# =========================
@router.message(F.text == "/start")
async def start(message: Message):

    # =========================
    # KEYBOARD MENU
    # =========================
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Add Bot to Group",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(text="📖 Help", callback_data="help"),
            InlineKeyboardButton(text="📊 Stats", callback_data="stats_menu")
        ],
        [
            InlineKeyboardButton(text="🛠 Panel (Owner)", callback_data="panel_menu")
        ]
    ])

    # =========================
    # TEXT MESSAGE
    # =========================
    await message.answer(
        "🤖 <b>ROSE STYLE GROUP MANAGER</b>\n\n"
        "👋 Welcome!\n\n"
        "📌 Bot ini membantu kamu mengelola group Telegram:\n"
        "• Anti spam system\n"
        "• Moderation tools\n"
        "• Welcome system\n"
        "• Warning system\n\n"
        "⚙️ Status: <b>ONLINE</b>\n"
        "🚀 Ready to manage your group\n\n"
        "📌 Step usage:\n"
        "1. Add bot ke group\n"
        "2. Jadikan admin\n"
        "3. Ketik /help di group\n",
        parse_mode="HTML",
        reply_markup=keyboard
    )
