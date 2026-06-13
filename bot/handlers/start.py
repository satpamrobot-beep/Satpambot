import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.state.admin_state import is_maintenance

from bot.db.database import get_pool

router = Router()

# =========================
# CONFIG
# =========================
CHANNEL = -1003777107004
GROUP = -1003721009353


# =========================
# DASHBOARD UI
# =========================
def dashboard_text(user, balance: int):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance / 16000

    return (
        "💠 <b>EarnFile System</b>\n"
        "──────────────\n\n"
        f"👤 {username}\n"
        f"🆔 <code>{user.id}</code>\n\n"
        f"💰 Rp {balance:,.0f} | $ {usd:.2f}\n\n"
        "──────────────\n"
        "<i>© 2026 EarnFileBot Telegram</i>"
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
            InlineKeyboardButton(text="⚙️ Setting", callback_data="setting"),
            InlineKeyboardButton(text="❓ Help", callback_data="help")
        ],
        [
            InlineKeyboardButton(text="ℹ️ About", callback_data="about")
        ],
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data="home")
        ]
    ])


# =========================
# JOIN BUTTON
# =========================
def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/+OzP85qRqCUhjMDE1")],
        [InlineKeyboardButton(text="👥 Join Group", url="https://t.me/+DTL9cOR34ipmM2U1")],
        [InlineKeyboardButton(text="🔄 Check Join", callback_data="cek_join")]
    ])


# =========================
# CHECK JOIN (ANTI BYPASS CORE)
# =========================
async def check_join(bot, user_id: int, chat: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
        return member.status in ("member", "administrator", "creator", "restricted")
    except Exception:
        return False


# =========================
# FORCE JOIN (FAST PARALLEL)
# =========================
async def force_join(bot, user_id: int) -> bool:
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
    except Exception:
        pass


# =========================
# GET BALANCE (REALTIME DB)
# =========================
async def get_balance(user_id: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT balance FROM users WHERE user_id=$1",
                user_id
            ) or 0
    except Exception:
        return 0


# =========================
# START COMMAND (MAX SPEED CORE)
# =========================

@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user

    # 🔴 MAINTENANCE BLOCK (INI YANG KAMU LUPA)
    if is_maintenance():
        await message.answer(
            "⚙️ Bot sedang maintenance\nSilakan coba lagi nanti"
        )
        return

    asyncio.create_task(save_user(user))

    if not await force_join(bot, user.id):
        await message.answer(
            "⚠️ Kamu wajib join channel & group dulu",
            reply_markup=join_kb()
        )
        return

    balance = await get_balance(user.id)

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

    if await force_join(bot, user_id):
        balance = await get_balance(user_id)

        await callback.message.edit_text(
            dashboard_text(callback.from_user, balance),
            reply_markup=home_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Belum join semua", show_alert=True)


# =========================
# HOME REFRESH (REALTIME UPDATE)
# =========================
@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery):

    # 🔴 MAINTENANCE CHECK (TARUH PALING ATAS)
    if is_maintenance():
        await callback.answer("⚙️ Bot sedang maintenance", show_alert=True)
        return

    user = callback.from_user
    balance = await get_balance(user.id)

    await callback.message.edit_text(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
