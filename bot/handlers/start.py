import asyncio
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart

from db.users import ensure_user
from bot.services.join import is_joined
from bot.services.wallet import get_balance

router = Router()


# =========================
# UI
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


def force_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Channel", url="https://t.me/yourchannel")],
        [InlineKeyboardButton(text="💬 Group", url="https://t.me/yourgroup")],
        [InlineKeyboardButton(text="✅ Check", callback_data="check_join")]
    ])


def format_dash(user, idr, usd):
    return (
        "🐧 <b>Bluebird Cede Earn</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{user.id}</code>\n"
        f"📛 Name: {user.full_name}\n"
        f"💰 Wallet: Rp {idr:,} / ${usd}\n"
        "━━━━━━━━━━━━━━"
    )


# =========================
# START (ULTRA FAST)
# =========================
@router.message(CommandStart())
async def start(message: Message):
    bot = message.bot
    user = message.from_user

    # ⚡ non-block DB write
    asyncio.create_task(
        ensure_user(user.id, user.username, user.full_name)
    )

    # ⚡ join check cached
    if not await is_joined(bot, user.id):
        await message.answer("⚠️ Join dulu bro", reply_markup=force_join_kb())
        return

    idr, usd = await get_balance(user.id)

    await message.answer(
        format_dash(user, idr, usd),
        reply_markup=dashboard_kb()
    )


# =========================
# CHECK JOIN CALLBACK
# =========================
@router.callback_query(F.data == "check_join")
async def check(call: CallbackQuery):
    bot = call.bot
    user = call.from_user

    if await is_joined(bot, user.id):
        await call.message.delete()

        idr, usd = await get_balance(user.id)

        await call.message.answer(
            format_dash(user, idr, usd),
            reply_markup=dashboard_kb()
        )
    else:
        await call.answer("❌ Belum join", show_alert=True)
