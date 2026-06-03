from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

# =========================
# DASHBOARD TEXT
# =========================
DASHBOARD = """
🤖 ROSE STYLE BOT ACTIVATED

📌 Status: ONLINE
🛠 Mode: PROTECTION SYSTEM v3

┌──────── SECURITY CORE ────────┐
[ 👋 Greeting ]   [ 🔒 Lock ]
[ 🧹 Filter ]     [ 🚫 AntiSpam ]
└───────────────────────────────┘

┌──────── ADVANCED SECURITY ─────┐
[ 🛡 Verification ]   [ ⚡ Force Join ]
[ ⏳ Join Delay ]      [ 🚫 Auto Kick ]
└───────────────────────────────┘

┌──────── CONTROL SYSTEM ────────┐
[ 🚫 Ban Tools ]      [ 📉 Flood Control ]
[ ⏳ Cooldown ]       [ 👀 Hidden Join/Leave ]
└───────────────────────────────┘

┌──────── ADMIN PANEL ───────────┐
[ ⚙️ Settings ]   [ 📊 Stats ]
[ 📖 Help ]
└───────────────────────────────┘
"""

# =========================
# MAIN KEYBOARD
# =========================
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👋 Greeting", callback_data="greet"),
            InlineKeyboardButton(text="🔒 Lock", callback_data="lock")
        ],
        [
            InlineKeyboardButton(text="🧹 Filter", callback_data="filter"),
            InlineKeyboardButton(text="🚫 AntiSpam", callback_data="antispam")
        ],
        [
            InlineKeyboardButton(text="🛡 Verification", callback_data="verify"),
            InlineKeyboardButton(text="⚡ Force Join", callback_data="force")
        ],
        [
            InlineKeyboardButton(text="⏳ Join Delay", callback_data="delay"),
            InlineKeyboardButton(text="🚫 Auto Kick", callback_data="autokick")
        ],
        [
            InlineKeyboardButton(text="📉 Flood", callback_data="flood"),
            InlineKeyboardButton(text="⏳ Cooldown", callback_data="cooldown")
        ],
        [
            InlineKeyboardButton(text="⚙️ Settings", callback_data="settings"),
            InlineKeyboardButton(text="📊 Stats", callback_data="stats")
        ],
        [
            InlineKeyboardButton(text="📖 Help", callback_data="help")
        ]
    ])

# =========================
# /start = DASHBOARD
# =========================
@router.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        DASHBOARD,
        reply_markup=main_kb()
    )

# =========================
# NAVIGATION (EDIT MESSAGE SYSTEM)
# =========================
@router.callback_query()
async def menu(call: CallbackQuery):

    data = call.data

    # semua tombol balikin ke dashboard dulu (simple system)
    if data in [
        "greet","lock","filter","antispam",
        "verify","force","delay","autokick",
        "flood","cooldown","settings","stats","help"
    ]:
        await call.message.edit_text(
            DASHBOARD + f"\n\n📌 Menu: {data.upper()} (COMING SOON)",
            reply_markup=main_kb()
        )

    await call.answer()
