import asyncio

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramBadRequest

from db.users import add_user, get_user_balance
from services.join import is_joined

router = Router()


# =========================
# FORCE JOIN BUTTON
# =========================
def force_join_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Join Channel",
                    url="https://t.me/+8TUGR4lwuzc4OTk1"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Join Group",
                    url="https://t.me/+1tipdp-NTywzODhl"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Check Join",
                    callback_data="check_join"
                )
            ]
        ]
    )


# =========================
# DASHBOARD BUTTONS
# =========================
def dashboard_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 UpFile", callback_data="upfile"),
                InlineKeyboardButton(text="📥 GetFile", callback_data="getfile")
            ],
            [
                InlineKeyboardButton(text="💳 Withdraw", callback_data="withdraw"),
                InlineKeyboardButton(text="👤 Account", callback_data="account")
            ],
            [
                InlineKeyboardButton(text="⚙️ Setting", callback_data="setting"),
                InlineKeyboardButton(text="📊 Statistik", callback_data="statistik")
            ],
            [
                InlineKeyboardButton(text="❓ Help", callback_data="help"),
                InlineKeyboardButton(text="ℹ️ About", callback_data="about")
            ]
        ]
    )


# =========================
# DASHBOARD TEXT
# =========================
def dashboard_text(user, balance_rp: int):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance_rp / 16000

    return (
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        "┃ 💰 <b>EARN FILE BOT</b> 🤖 ┃\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        f"👤 User : {username}\n"
        f"🆔 ID   : <code>{user.id}</code>\n"
        f"💳 Balance : Rp {balance_rp:,.0f}  •  $ {usd:.2f}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚀 Upload • Share • Earn\n"
        "━━━━━━━━━━━━━━━━━━"
    )


# =========================
# START
# =========================
@router.message(CommandStart())
async def start(message: Message):
    user = message.from_user

    try:
        await add_user(user.id, user.username, user.first_name)
    except:
        pass

    if not await is_joined(message.bot, user.id):
        await message.answer(
            "⚠️ Join channel & group dulu sebelum lanjut.",
            reply_markup=force_join_kb()
        )
        return

    balance = await get_user_balance(user.id)

    await message.answer(
        dashboard_text(user, balance),
        reply_markup=dashboard_kb()
    )


# =========================
# CHECK JOIN
# =========================
@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    user = call.from_user

    if not await is_joined(call.bot, user.id):
        return await call.answer("❌ Kamu belum join semua", show_alert=True)

    balance = await get_user_balance(user.id)

    try:
        await call.message.edit_text(
            dashboard_text(user, balance),
            reply_markup=dashboard_kb()
        )
    except TelegramBadRequest:
        pass

    await call.answer()


# =========================
# BACK HOME
# =========================
@router.callback_query(F.data == "back_home")
async def back_home(call: CallbackQuery):
    user = call.from_user
    balance = await get_user_balance(user.id)

    try:
        await call.message.edit_text(
            dashboard_text(user, balance),
            reply_markup=dashboard_kb()
        )
    except TelegramBadRequest:
        pass

    await call.answer()


# =========================
# GET FILE (FIX + LINK START FORMAT)
# =========================
@router.callback_query(F.data == "getfile")
async def getfile(call: CallbackQuery):
    code = "FLIW5SXKQY6G"  # nanti ini ambil dari DB

    link = f"https://t.me/decodefilebot?start=decodefilebot_{code}"

    await call.message.edit_text(
        "📥 GET FILE\n\n"
        f"🔗 Link kamu:\n{link}\n\n"
        "Klik link untuk akses file."
    )

    await call.answer()
