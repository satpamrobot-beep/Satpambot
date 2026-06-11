from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


# =========================
# UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery):
    await call.message.edit_text("📤 Upload file mode aktif")
    await call.answer()


# =========================
# GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile(call: CallbackQuery):
    await call.message.edit_text("📥 Kirim code file kamu")
    await call.answer()


# =========================
# WITHDRAW
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    await call.message.edit_text("💳 Withdraw page")
    await call.answer()


# =========================
# ACCOUNT
# =========================
@router.callback_query(F.data == "account")
async def account(call: CallbackQuery):
    await call.message.edit_text("👤 Account info")
    await call.answer()


# =========================
# SETTING
# =========================
@router.callback_query(F.data == "setting")
async def setting(call: CallbackQuery):
    await call.message.edit_text("⚙️ Setting menu")
    await call.answer()


# =========================
# STATISTIK
# =========================
@router.callback_query(F.data == "statistik")
async def statistik(call: CallbackQuery):
    await call.message.edit_text("📊 Statistik bot")
    await call.answer()


# =========================
# HELP
# =========================
@router.callback_query(F.data == "help")
async def help_menu(call: CallbackQuery):
    await call.message.edit_text("❓ Help center")
    await call.answer()


# =========================
# ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    await call.message.edit_text("ℹ️ About bot")
    await call.answer()
