import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.database import get_pool

router = Router()


# =========================
# CONFIG
# =========================
CHANNEL = -1003777107004
GROUP = -1003721009353


# =========================
# COPYRIGHT
# =========================
def copyright_text():
    return "━━━━━━━━━━━━━━\n<i>© 2026 EarnFileBot Telegram</i>"


# =========================
# DASHBOARD
# =========================
def dashboard_text(user, balance_rp: int):
    return (
        "📦 <b>EarnFileBot - File Sharing Platform</b>\n\n"
        f"🆔 <b>ID Akun:</b> <code>{user.id}</code>\n"
        f"💰 <b>Total Saldo:</b> Rp {balance_rp:,.0f}\n"
        f"👥 <b>Mengundang:</b> 0 users\n\n"
        f"{copyright_text()}"
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
            InlineKeyboardButton(text="⚙️ Setting", callback_data="setting")
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about")
        ]
    ])


# =========================
# JOIN BUTTON
# =========================
def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/your_channel")],
        [InlineKeyboardButton(text="👥 Join Group", url="https://t.me/your_group")],
        [InlineKeyboardButton(text="🔄 Check Join", callback_data="cek_join")]
    ])


# =========================
# CHECK JOIN (ANTI BYPASS CORE)
# =========================
async def check_join(bot, user_id: int, chat: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)

        return member.status in (
            "member",
            "administrator",
            "creator",
            "restricted"
        )

    except Exception as e:
        print(f"[JOIN ERROR] chat={chat} user={user_id} -> {e}")
        return False


# =========================
# FORCE VERIFY (ANTI BYPASS LAYER)
# =========================
async def force_verify(bot, user_id: int) -> bool:
    ch = await check_join(bot, user_id, CHANNEL)
    gp = await check_join(bot, user_id, GROUP)
    return ch and gp


# =========================
# SAVE USER (NON-BLOCKING)
# =========================
async def save_user(user):
    pool = get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.username)


# =========================
# START (FAST + BALANCE + FORCE JOIN)
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user

    # async save biar tidak delay
    asyncio.create_task(save_user(user))

    # force join check (ANTI BYPASS)
    if not await force_verify(bot, user.id):
        await message.answer(
            "⚠️ You must join channel & group first",
            reply_markup=join_kb()
        )
        return

    # ambil balance dari DB
    pool = get_pool()
    async with pool.acquire() as conn:
        balance = await conn.fetchval(
            "SELECT balance FROM users WHERE user_id=$1",
            user.id
        )

    if balance is None:
        balance = 0

    # dashboard
    await message.answer(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )


# =========================
# CHECK JOIN CALLBACK
# =========================
@router.callback_query(F.data == "cek_join")
async def cek_join(callback: CallbackQuery, bot):
    user_id = callback.from_user.id

    if await force_verify(bot, user_id):
        pool = get_pool()

        async with pool.acquire() as conn:
            balance = await conn.fetchval(
                "SELECT balance FROM users WHERE user_id=$1",
                user_id
            )

        if balance is None:
            balance = 0

        await callback.message.edit_text(
            dashboard_text(callback.from_user, balance),
            reply_markup=home_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Not joined yet", show_alert=True)


# =========================
# HOME REFRESH
# =========================
@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    user = callback.from_user

    pool = get_pool()

    async with pool.acquire() as conn:
        balance = await conn.fetchval(
            "SELECT balance FROM users WHERE user_id=$1",
            user.id
        )

    if balance is None:
        balance = 0

    await callback.message.edit_text(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
