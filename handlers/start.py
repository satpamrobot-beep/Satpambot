import asyncio

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart

from config import FORCE_CHANNEL
from db.users import add_user, get_user_balance
from services.join import is_joined

router = Router()


# =========================
# FORCE JOIN BUTTON
# =========================
def force_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
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
    ])


# =========================
# DASHBOARD BUTTONS
# =========================
def dashboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 UpFile", callback_data="upfile"),
            InlineKeyboardButton(text="📥 GetFile", callback_data="getfile"),
        ],
        [
            InlineKeyboardButton(text="💳 Withdraw", callback_data="withdraw"),
            InlineKeyboardButton(text="👤 Account", callback_data="account"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Setting", callback_data="setting"),
            InlineKeyboardButton(text="📊 Statistik", callback_data="statistik"),
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
        ],
    ])


# =========================
# DASHBOARD TEXT
# =========================
def dashboard_text(user, balance: int):
    username = f"@{user.username}" if user.username else "-"

    return (
        "💰 <b>Earn File Bot 🤖</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🆔 ID : <code>{user.id}</code>\n"
        f"👤 Username : {username}\n"
        f"💰 Balance : Rp {balance:,}\n"
        "━━━━━━━━━━━━━━"
    )


# =========================
# START COMMAND
# =========================
@router.message(CommandStart())
async def start(message: Message):
    user = message.from_user

    # SAVE USER (NO SILENT FAIL)
    try:
        await add_user(user.id, user.username, user.full_name)
    except Exception as e:
        print("[add_user error]", e)

    # FORCE JOIN CHECK
    if not await is_joined(message.bot, user.id):
        await message.answer(
            "⚠️ Kamu harus join dulu sebelum lanjut",
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

    if await is_joined(call.bot, user.id):
        balance = await get_user_balance(user.id)

        await call.message.edit_text(
            dashboard_text(user, balance),
            reply_markup=dashboard_kb()
        )
        await call.answer()
    else:
        await call.answer("❌ Kamu belum join semua", show_alert=True)
