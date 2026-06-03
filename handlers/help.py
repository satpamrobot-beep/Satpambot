from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from config import OWNER_ID

router = Router()

# =========================
# HELP CONTENT (PAGES)
# =========================
PAGES = {
    1: "📖 <b>ROSE HELP SYSTEM</b>\n\n"
       "🤖 Group Manager Bot\n"
       "⚙️ Anti spam • moderation • tools\n\n"
       "👉 Gunakan tombol di bawah",

    2: "👮 <b>MODERATION</b>\n\n"
       "🚫 /ban (reply)\n"
       "👢 /kick (reply)\n"
       "🔇 /mute (reply)\n"
       "🔊 /unmute (reply)\n"
       "⚠️ /warn (reply)",

    3: "⚙️ <b>SETUP GUIDE</b>\n\n"
       "1. Add bot\n"
       "2. Make admin\n"
       "3. Enable permissions\n"
       "4. Done",

    4: "🛠 <b>HOW TO USE</b>\n\n"
       "👤 User join → follow rules\n"
       "👮 Admin → moderation commands\n"
       "👑 Owner → /panel",

    5: "📊 <b>SYSTEM STATUS</b>\n\n"
       "⚡ Online\n"
       "🧠 Stable\n"
       "🚀 Production mode"
}

TOTAL = len(PAGES)

# =========================
# MAIN KEYBOARD UI
# =========================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👮 Moderation", callback_data="h:mod"),
            InlineKeyboardButton(text="⚙️ Setup", callback_data="h:setup")
        ],
        [
            InlineKeyboardButton(text="🛠 Guide", callback_data="h:guide"),
            InlineKeyboardButton(text="📊 Stats", callback_data="h:stats")
        ],
        [
            InlineKeyboardButton(text="🤖 AI Help", callback_data="h:ai")
        ]
    ])

# =========================
# NAVIGATION KEYBOARD (PAGE)
# =========================
def page_keyboard(page: int):
    nav = []

    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"p:{page-1}"))

    if page < TOTAL:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"p:{page+1}"))

    buttons = []
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton(text="🏠 Home", callback_data="p:1")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

# =========================
# /HELP ENTRY
# =========================
@router.message(F.text == "/help")
async def help_start(message: Message):

    await message.answer(
        PAGES[1],
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )

# =========================
# PAGE NAVIGATION
# =========================
@router.callback_query(F.data.startswith("p:"))
async def pages(callback: CallbackQuery):

    page = int(callback.data.split(":")[1])

    await callback.message.edit_text(
        PAGES.get(page, PAGES[1]),
        parse_mode="HTML",
        reply_markup=page_keyboard(page)
    )

    await callback.answer()

# =========================
# MAIN MENU BUTTON HANDLERS
# =========================
@router.callback_query(F.data == "h:mod")
async def mod(callback: CallbackQuery):

    await callback.message.edit_text(
        PAGES[2],
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "h:setup")
async def setup(callback: CallbackQuery):

    await callback.message.edit_text(
        PAGES[3],
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "h:guide")
async def guide(callback: CallbackQuery):

    await callback.message.edit_text(
        PAGES[4],
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "h:stats")
async def stats(callback: CallbackQuery):

    await callback.message.edit_text(
        PAGES[5],
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()

# =========================
# AI HELP MODE (SIMPLE)
# =========================
@router.callback_query(F.data == "h:ai")
async def ai_help(callback: CallbackQuery):

    await callback.message.edit_text(
        "🤖 <b>AI HELP MODE</b>\n\n"
        "Gunakan:\n"
        "/aihelp ban\n"
        "/aihelp mute\n"
        "/aihelp setup\n\n"
        "💡 Bot akan bantu jawab otomatis",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )
    await callback.answer()

# =========================
# SEARCH HELP SYSTEM
# =========================
SEARCH_DB = {
    "ban": "🚫 /ban (reply user)",
    "kick": "👢 /kick (reply user)",
    "mute": "🔇 /mute (reply user)",
    "warn": "⚠️ /warn (reply user, auto ban 3x)",
    "setup": "⚙️ add bot → admin → enable permissions"
}

@router.message(F.text.startswith("/help "))
async def search(message: Message):

    query = message.text.replace("/help", "").strip().lower()

    result = SEARCH_DB.get(query)

    if result:
        await message.answer(
            f"🔎 <b>RESULT</b>\n\n{result}",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ Not found\n\nTry:\n/help ban\n/help mute\n/help setup"
        )

# =========================
# ROLE HELP (OPTIONAL)
# =========================
def get_role(user_id: int):
    if user_id == OWNER_ID:
        return "owner"
    return "user"

@router.message(F.text == "/help_role")
async def role_help(message: Message):

    role = get_role(message.from_user.id)

    if role == "owner":
        text = "👑 OWNER\n/panel /broadcast /maintenance"
    else:
        text = "👤 USER\nJoin group & enjoy"

    await message.answer(text)
