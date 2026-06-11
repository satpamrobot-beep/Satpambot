from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.services.wallet import get_balance
from bot.keyboards.user import dashboard_kb

router = Router()

def page(title: str):
    return f"{title}\n━━━━━━━━━━━━━━\n🚧 Coming soon..."


@router.callback_query(F.data == "back_home")
async def back_home(call: CallbackQuery):
    user = call.from_user
    idr, usd = await get_balance(user.id)

    text = (
        "🐧 <b>Bluebird CodeEarn</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{user.id}</code>\n"
        f"💰 Wallet: Rp {idr:,} / ${usd}\n"
        "━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(text, reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "account")
async def account(call: CallbackQuery):
    user = call.from_user
    idr, usd = await get_balance(user.id)

    text = (
        "👤 <b>ACCOUNT INFO</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"ID: <code>{user.id}</code>\n"
        f"Name: {user.full_name}\n"
        f"Balance: Rp {idr:,} / ${usd}\n"
    )

    await call.message.edit_text(text, reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "withdraw")
async def withdraw(call: CallbackQuery):
    await call.message.edit_text(page("💳 WITHDRAW"), reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery):
    await call.message.edit_text(page("📤 UPFILE"), reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "getfile")
async def getfile(call: CallbackQuery):
    await call.message.edit_text(page("📥 GETFILE"), reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "setting")
async def setting(call: CallbackQuery):
    await call.message.edit_text(page("⚙️ SETTING"), reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "statistik")
async def statistik(call: CallbackQuery):
    await call.message.edit_text(page("📊 STATISTIK"), reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "help")
async def help(call: CallbackQuery):
    await call.message.edit_text(page("❓ HELP"), reply_markup=dashboard_kb())
    await call.answer()


@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ <b>About Bot</b>\n━━━━━━━━━━━━━━\nBluebird Earn v1",
        reply_markup=dashboard_kb()
    )
    await call.answer()
