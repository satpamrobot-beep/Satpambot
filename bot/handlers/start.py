import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart

from db.users import ensure_user, get_balance
from bot.services.join import is_joined

router = Router()

ADMIN_IDS = [6847035364]

CHANNEL_ID = -1003712587847
GROUP_ID = -1003920865154


# =========================
# DASHBOARD KEYBOARD
# =========================
def dashboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 UpFile", callback_data="upfile"),
            InlineKeyboardButton(text="📥 GetFile", callback_data="getfile"),
        ],
        [
            InlineKeyboardButton(text="👤 Account", callback_data="account"),
            InlineKeyboardButton(text="💳 Withdraw", callback_data="withdraw"),
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
# FORCE JOIN
# =========================
def force_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Channel", url="https://t.me/yourchannel")],
        [InlineKeyboardButton(text="💬 Group", url="https://t.me/yourgroup")],
        [InlineKeyboardButton(text="✅ Check", callback_data="check_join")]
    ])


# =========================
# FORMAT DASHBOARD
# =========================
def format_dashboard(user, idr, usd):
    return (
        "🐧 <b>Bluebird Cede Earn</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{user.id}</code>\n"
        f"📛 Name: {user.full_name}\n"
        f"💰 Wallet: Rp {idr:,} / ${usd}\n"
        "━━━━━━━━━━━━━━"
    )


# =========================
# START COMMAND
# =========================
@router.message(CommandStart())
async def start(message: Message):
    bot = message.bot
    user = message.from_user

    # create user async safe
    asyncio.create_task(
        ensure_user(user.id, user.username, user.full_name)
    )

    # join check
    if not await is_joined(bot, user.id):
        await message.answer("⚠️ Join dulu untuk lanjut", reply_markup=force_join_kb())
        return

    idr, usd = await get_balance(user.id)

    await message.answer(
        format_dashboard(user, idr, usd),
        reply_markup=dashboard_kb()
    )

    # admin button
    if user.id in ADMIN_IDS:
        await message.answer(
            "👑 Admin detected",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Open Admin Panel", callback_data="admin_panel")]
            ])
        )


# =========================
# CHECK JOIN CALLBACK
# =========================
@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    bot = call.bot
    user = call.from_user

    if await is_joined(bot, user.id):
        await call.message.delete()
        idr, usd = await get_balance(user.id)

        await call.message.answer(
            format_dashboard(user, idr, usd),
            reply_markup=dashboard_kb()
        )
    else:
        await call.answer("❌ Belum join semua", show_alert=True)


# =========================
# BACK HOME
# =========================
@router.callback_query(F.data == "back_home")
async def back_home(call: CallbackQuery):
    user = call.from_user
    idr, usd = await get_balance(user.id)

    await call.message.edit_text(
        format_dashboard(user, idr, usd),
        reply_markup=dashboard_kb()
    )
    await call.answer()


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
        f"🆔 ID      : <code>{user.id}</code>\n"
        f"📛 Name    : {user.full_name}\n"
        f"👤 Username: @{user.username if user.username else '-'}\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 Balance : Rp {idr:,} / ${usd}\n"
        "━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(text, reply_markup=dashboard_kb())
    await call.answer()


# =========================
# SIMPLE PAGE TEMPLATE
# =========================
def page(title: str):
    return f"{title}\n━━━━━━━━━━━━━━\n🚧 Coming soon..."


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
        "ℹ️ <b>About Bot</b>\n━━━━━━━━━━━━━━\nBluebird Earn System v1",
        reply_markup=dashboard_kb()
    )
    await call.answer()
