from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.services.wallet import get_balance

router = Router()


# =========================
# FORMAT TEXT
# =========================
def account_text(user, idr, usd):
    username = f"@{user.username}" if user.username else "-"

    return (
        "👤 <b>ACCOUNT INFO</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"ID      : <code>{user.id}</code>\n"
        f"Name    : {user.full_name}\n"
        f"Username: {username}\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 Balance: Rp {idr:,} / ${usd:.2f}\n"
    )


def simple_text(title: str):
    return (
        f"{title}\n"
        "━━━━━━━━━━━━━━\n"
        "🚧 Coming soon..."
    )


# =========================
# ACCOUNT
# =========================
@router.callback_query(F.data == "account")
async def account(call: CallbackQuery):
    user = call.from_user
    idr, usd = await get_balance(user.id)

    await call.message.edit_text(account_text(user, idr, usd))
    await call.answer()


# =========================
# WITHDRAW
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    await call.message.edit_text(simple_text("💳 WITHDRAW"))
    await call.answer()


# =========================
# UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery):
    await call.message.edit_text(simple_text("📤 UPFILE"))
    await call.answer()


# =========================
# GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile(call: CallbackQuery):
    await call.message.edit_text(simple_text("📥 GETFILE"))
    await call.answer()


# =========================
# SETTING
# =========================
@router.callback_query(F.data == "setting")
async def setting(call: CallbackQuery):
    await call.message.edit_text(simple_text("⚙️ SETTING"))
    await call.answer()


# =========================
# STATISTIK
# =========================
@router.callback_query(F.data == "statistik")
async def statistik(call: CallbackQuery):
    await call.message.edit_text(simple_text("📊 STATISTIK"))
    await call.answer()


# =========================
# HELP
# =========================
@router.callback_query(F.data == "help")
async def help(call: CallbackQuery):
    await call.message.edit_text(simple_text("❓ HELP"))
    await call.answer()


# =========================
# ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>About Bot</b>\n━━━━━━━━━━━━━━\nBluebird Earn System v1"
    )
    await call.answer()
