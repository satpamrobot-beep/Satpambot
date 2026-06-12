import asyncio
import time

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.database import get_pool

router = Router()


# =========================
# CONFIG
# =========================
CHANNEL = -1003777107004
GROUP = -1003721009353

CACHE = {}
CACHE_TTL = 10  # fast cache


# =========================
# UI DASHBOARD
# =========================
def dashboard_text(user, balance: int):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance / 16000

    return (
        "💠 <b>EarnFile</b>\n"
        "──────────────\n\n"
        f"👤 {username}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"💰 Rp {balance:,.0f} | $ {usd:.2f}\n\n"
        "──────────────\n"
        "<i>© 2026 EarnFileBot Telegram</i>"
    )


# =========================
# HOME BUTTON
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
            InlineKeyboardButton(text="⚙️ Setting", callback_data="setting"),
            InlineKeyboardButton(text="❓ Help", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="ℹ️ About", callback_data="about")
        ]
    ])


# =========================
# JOIN CHECK (FAST SAFE)
# =========================
async def check_join(bot, user_id: int, chat: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except:
        return False


# =========================
# FORCE VERIFY (ANTI BYPASS MAX)
# =========================
async def force_verify(bot, user_id: int) -> bool:
    ch, gp = await asyncio.gather(
        check_join(bot, user_id, CHANNEL),
        check_join(bot, user_id, GROUP)
    )
    return ch and gp


# =========================
# SAVE USER (NON BLOCKING)
# =========================
async def save_user(user):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO NOTHING
            """, user.id, user.username)
    except:
        pass


# =========================
# GET BALANCE (CACHE + DB SAFE)
# =========================
async def get_balance(user_id: int):
    now = time.time()

    if user_id in CACHE:
        bal, ts = CACHE[user_id]
        if now - ts < CACHE_TTL:
            return bal

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            bal = await conn.fetchval(
                "SELECT COALESCE(balance,0) FROM users WHERE user_id=$1",
                user_id
            )

        CACHE[user_id] = (bal, now)
        return bal

    except:
        return 0


# =========================
# START (MAX SPEED CORE)
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user

    # non-blocking save (NO DELAY)
    asyncio.create_task(save_user(user))

    # FORCE JOIN CHECK
    if not await force_verify(bot, user.id):
        await message.answer(
            "⚠️ Kamu wajib join channel & group dulu",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/your_channel")],
                [InlineKeyboardButton(text="👥 Join Group", url="https://t.me/your_group")],
                [InlineKeyboardButton(text="🔄 Cek Join", callback_data="cek_join")]
            ])
        )
        return

    # GET BALANCE FAST
    balance = await get_balance(user.id)

    await message.answer(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )


# =========================
# CHECK JOIN BUTTON
# =========================
@router.callback_query(F.data == "cek_join")
async def cek_join(callback: CallbackQuery, bot):
    user_id = callback.from_user.id

    if await force_verify(bot, user_id):
        balance = await get_balance(user_id)

        await callback.message.edit_text(
            dashboard_text(callback.from_user, balance),
            reply_markup=home_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Kamu belum join semua", show_alert=True)


# =========================
# HOME REFRESH
# =========================
@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    user = callback.from_user

    balance = await get_balance(user.id)

    await callback.message.edit_text(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
