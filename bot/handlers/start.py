import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart

from db.users import ensure_user, get_balance
from bot.services.join import is_joined

router = Router()

ADMIN_IDS = [6847035364]

CHANNEL_ID = -1003712587847
GROUP_ID = -1003920865154


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
# DASHBOARD
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
# FORMAT
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
# START (FAST + SAFE)
# =========================
@router.message(CommandStart())
async def start(message: Message):
    bot = message.bot
    user = message.from_user

    # ⚡ jangan pakai create_task (biar stabil)
    await ensure_user(user.id, user.username, user.full_name)

    # ⚡ join check
    if not await is_joined(bot, user.id):
        await message.answer("⚠️ Join dulu", reply_markup=force_join_kb())
        return

    idr, usd = await get_balance(user.id)

    await message.answer(
        format_dashboard(user, idr, usd),
        reply_markup=dashboard_kb()
    )

    # =========================
    # ADMIN PANEL BUTTON
    # =========================
    if user.id in ADMIN_IDS:
        await message.answer(
            "👑 Admin detected",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Open Admin Panel",
                    callback_data="admin_panel"
                )]
            ])
        )


# =========================
# CHECK JOIN
# =========================
@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    bot = call.bot
    user = call.from_user

    await ensure_user(user.id, user.username, user.full_name)

    if await is_joined(bot, user.id):
        try:
            await call.message.delete()
        except:
            pass

        idr, usd = await get_balance(user.id)

        await call.message.answer(
            format_dashboard(user, idr, usd),
            reply_markup=dashboard_kb()
        )
    else:
        await call.answer("❌ Belum join", show_alert=True)
