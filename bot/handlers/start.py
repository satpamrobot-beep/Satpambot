import asyncio
import time

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.database import get_pool

router = Router()

CHANNEL = -1003777107004
GROUP = -1003721009353

BAL_CACHE = {}
CACHE_TTL = 10


# =========================
# DASHBOARD
# =========================
def dashboard_text(user, balance, level):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance / 16000

    return (
        "💠 <b>EarnFile System Pro</b>\n"
        "──────────────\n\n"
        f"👤 {username}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"🏆 Level: <b>{level}</b>\n\n"
        f"💰 Rp {balance:,.0f} | $ {usd:.2f}\n\n"
        "──────────────\n"
        "<i>© 2026 EarnFileBot</i>"
    )


# =========================
# KB
# =========================
def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("📤 Upload", callback_data="upload"),
            InlineKeyboardButton("🔑 Code", callback_data="open_code")
        ],
        [
            InlineKeyboardButton("👤 Account", callback_data="account"),
            InlineKeyboardButton("📦 Product", callback_data="my_product")
        ],
        [
            InlineKeyboardButton("⚙️ Setting", callback_data="setting"),
            InlineKeyboardButton("❓ Help", callback_data="help")
        ]
    ])


def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📢 Channel", url="https://t.me/your_channel")],
        [InlineKeyboardButton("👥 Group", url="https://t.me/your_group")],
        [InlineKeyboardButton("🔄 Verify", callback_data="cek_join")]
    ])


# =========================
# JOIN CHECK
# =========================
async def check_join(bot, user_id: int, chat: int):
    try:
        m = await bot.get_chat_member(chat, user_id)
        return m.status in ("member", "administrator", "creator", "restricted")
    except:
        return False


async def force_verify(bot, user_id: int):
    ch, gp = await asyncio.gather(
        check_join(bot, user_id, CHANNEL),
        check_join(bot, user_id, GROUP)
    )
    return ch and gp


# =========================
# DB HELPERS
# =========================
async def get_user_data(user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT balance, level FROM users WHERE user_id=$1",
            user_id
        )


async def save_user(user):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, balance, level)
            VALUES ($1,$2,0,1)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.username)


# =========================
# LEVEL SYSTEM
# =========================
def calc_level(balance: int):
    if balance >= 5_000_000:
        return 5
    if balance >= 2_000_000:
        return 4
    if balance >= 500_000:
        return 3
    if balance >= 100_000:
        return 2
    return 1


# =========================
# BALANCE CACHE
# =========================
async def get_balance(user_id: int):
    now = time.time()

    if user_id in BAL_CACHE:
        b, t = BAL_CACHE[user_id]
        if now - t < CACHE_TTL:
            return b

    pool = get_pool()
    async with pool.acquire() as conn:
        bal = await conn.fetchval(
            "SELECT balance FROM users WHERE user_id=$1",
            user_id
        ) or 0

    BAL_CACHE[user_id] = (bal, now)
    return bal


# =========================
# START
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user

    asyncio.create_task(save_user(user))

    if not await force_verify(bot, user.id):
        await message.answer(
            "⚠️ Join dulu channel & group",
            reply_markup=join_kb()
        )
        return

    data = await get_user_data(user.id)
    balance = data["balance"] if data else 0
    level = data["level"] if data else 1

    level = calc_level(balance)

    await message.answer(
        dashboard_text(user, balance, level),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )


# =========================
# CHECK JOIN
# =========================
@router.callback_query(F.data == "cek_join")
async def cek_join(callback, bot):
    user_id = callback.from_user.id

    if await force_verify(bot, user_id):
        data = await get_user_data(user_id)
        balance = data["balance"]
        level = calc_level(balance)

        await callback.message.edit_text(
            dashboard_text(callback.from_user, balance, level),
            reply_markup=home_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Belum join", show_alert=True)
