from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.services.wallet import get_balance

router = Router()


# =========================
# ACCOUNT
# =========================
@router.callback_query(F.data == "account")
async def account(call: CallbackQuery):
    user = call.from_user
    idr, usd = await get_balance(user.id)

    text = (
        "👤 <b>ACCOUNT INFO</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"ID      : <code>{user.id}</code>\n"
        f"Name    : {user.full_name}\n"
        f"Username: @{user.username if user.username else '-'}\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 Balance: Rp {idr:,} / ${usd}\n"
    )

    await call.message.answer(text)
    await call.answer()


# =========================
# WITHDRAW (DUMMY DULU)
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    await call.message.answer(
        "💳 <b>Withdraw System</b>\n\n"
        "Fitur masih dalam pengembangan."
    )
    await call.answer()


# =========================
# UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery):
    await call.message.answer("📤 Upload file fitur coming soon")
    await call.answer()


# =========================
# GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile(call: CallbackQuery):
    await call.message.answer("📥 Get file fitur coming soon")
    await call.answer()


# =========================
# SETTING
# =========================
@router.callback_query(F.data == "setting")
async def setting(call: CallbackQuery):
    await call.message.answer(
        "⚙️ <b>Settings</b>\n\n- Not available yet"
    )
    await call.answer()


# =========================
# STATISTIK
# =========================
@router.callback_query(F.data == "statistik")
async def statistik(call: CallbackQuery):
    await call.message.answer(
        "📊 <b>Statistik</b>\n\n- Coming soon"
    )
    await call.answer()


# =========================
# HELP
# =========================
@router.callback_query(F.data == "help")
async def help(call: CallbackQuery):
    await call.message.answer(
        "❓ <b>Help Center</b>\n\nHubungi admin untuk bantuan."
    )
    await call.answer()


# =========================
# ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    await call.message.answer(
        "ℹ️ <b>About Bot</b>\n\nBluebird Earn System v1"
    )
    await call.answer()
