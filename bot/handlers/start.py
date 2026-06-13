import asyncio
import time

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.database import get_pool

router = Router()

CHANNEL = -1003777107004
GROUP = -1003721009353

CACHE = {}
CACHE_TTL = 10


# =========================
# DASHBOARD
# =========================
def dashboard(user, balance):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance / 16000

    return (
        "💠 <b>EarnFile System</b>\n"
        "──────────────\n\n"
        f"👤 {username}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"💰 Rp {balance:,.0f} | $ {usd:.2f}\n\n"
        "──────────────\n"
        "<i>© 2026 EarnFileBot</i>"
    )


# =========================
# HOME KEYBOARD
# =========================
def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Upload", callback_data="upload"),
            InlineKeyboardButton(text="🔑 Code", callback_data="open_code")
        ],
        [
            InlineKeyboardButton(text="👤 Account", callback_data="account"),
            InlineKeyboardButton(text="📦 Product", callback_data="my_product")
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data="home")
        ]
    ])


# =========================
# JOIN CHECK
# =========================
async def check_join(bot, user_id, chat):
    try:
        m = await bot.get_chat_member(chat, user_id)
        return m.status in ("member", "administrator", "creator", "restricted")
    except:
        return False


async def force_join(bot, user_id):
    return all(await asyncio.gather(
        check_join(bot, user_id, CHANNEL),
        check_join(bot, user_id, GROUP)
    ))


# =========================
# DB
# =========================
async def get_balance(user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT balance FROM users WHERE user_id=$1",
            user_id
        ) or 0


async def save_user(user):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, balance)
            VALUES ($1,$2,0)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.username)


# =========================
# START
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user

    asyncio.create_task(save_user(user))

    if not await force_join(bot, user.id):
        await message.answer("⚠️ Join dulu channel & group")
        return

    balance = await get_balance(user.id)

    await message.answer(
        dashboard(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )


# =========================
# HOME REFRESH
# =========================
@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    user = callback.from_user

    balance = await get_balance(user.id)

    await callback.message.edit_text(
        dashboard(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
