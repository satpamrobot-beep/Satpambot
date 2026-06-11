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
        f"🆔 ID      : <code>{user.id}</code>\n"
        f"📛 Name    : {user.full_name}\n"
        f"👤 Username: {username}\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 Balance : Rp {idr:,} / ${usd}\n"
        "━━━━━━━━━━━━━━"
    )


def page_text(title: str):
    return (
        f"{title}\n"
        "━━━━━━━━━━━━━━\n"
        "🚧 Coming soon..."
    )


# =========================
# SAFE EDIT FUNCTION
# =========================
async def safe_edit(call: CallbackQuery, text: str, kb):
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except:
        # fallback kalau edit gagal (Telegram limit / same text)
        await call.message.answer(text, reply_markup=kb)


# =========================
# ACCOUNT
# =========================
@router.callback_query(F.data == "account")
async def account(call: CallbackQuery):
    user = call.from_user
    idr, usd = await get_balance(user.id)

    await safe_edit(
        call,
        account_text(user, idr, usd),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# WITHDRAW
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    await safe_edit(
        call,
        page_text("💳 WITHDRAW SYSTEM"),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery):
    await safe_edit(
        call,
        page_text("📤 UPFILE SYSTEM"),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# GETFILE
# =========================
@router.callback_query(F.data == "getfile")
async def getfile(call: CallbackQuery):
    await safe_edit(
        call,
        page_text("📥 GETFILE SYSTEM"),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# SETTING
# =========================
@router.callback_query(F.data == "setting")
async def setting(call: CallbackQuery):
    await safe_edit(
        call,
        page_text("⚙️ SETTINGS"),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# STATISTIK
# =========================
@router.callback_query(F.data == "statistik")
async def statistik(call: CallbackQuery):
    await safe_edit(
        call,
        page_text("📊 STATISTIK BOT"),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# HELP
# =========================
@router.callback_query(F.data == "help")
async def help(call: CallbackQuery):
    await safe_edit(
        call,
        page_text("❓ HELP CENTER"),
        call.message.reply_markup
    )
    await call.answer()


# =========================
# ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    await safe_edit(
        call,
        "ℹ️ <b>ABOUT BOT</b>\n━━━━━━━━━━━━━━\nBluebird Earn System v1.0",
        call.message.reply_markup
    )
    await call.answer()
