from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_USERNAME

router = Router()

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
            InlineKeyboardButton(text="📊 Stats", callback_data="stats_menu")
        ]
    ])

    await message.answer(
        "🤖 <b>ROSE STYLE BOT</b>\n\n"
        "👋 Hello!\n\n"
        "📌 Cara pakai bot:\n"
        "1. Add bot ke group\n"
        "2. Jadikan admin\n"
        "3. Gunakan /help di group\n\n"
        "⚙️ Status: Online\n"
        "🚀 Ready to manage your group",
        parse_mode="HTML",
        reply_markup=keyboard
    )
