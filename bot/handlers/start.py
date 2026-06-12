from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.database import get_pool

router = Router()


# =========================
# CONFIG
# =========================
CHANNEL = "https://t.me/+OzP85qRqCUhjMDE1"
GROUP = "https://t.me/+DTL9cOR34ipmM2U1"


# =========================
# DASHBOARD UI
# =========================
def dashboard_text(user, balance_rp: int):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance_rp / 16000

    return (
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        "┃ 💰 <b>EARN FILE BOT</b> ┃\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        f"👤 User : {username}\n"
        f"🆔 ID   : <code>{user.id}</code>\n"
        f"💳 Balance : Rp {balance_rp:,.0f} • $ {usd:.2f}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚀 Upload • Share • Earn"
    )


# =========================
# HOME BUTTON
# =========================
def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Upload", callback_data="upload"),
            InlineKeyboardButton(text="🔎 Buka Code", callback_data="open_code")
        ],
        [
            InlineKeyboardButton(text="🧾 My Account", callback_data="account")
        ],
        [
            InlineKeyboardButton(text="📦 Produk", callback_data="my_product"),
            InlineKeyboardButton(text="⚙️ Setting", callback_data="setting")
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about")
        ]
    ])


# =========================
# JOIN PANEL
# =========================
def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Join Channel", url=f"https://t.me/{CHANNEL.replace('@','')}")
        ],
        [
            InlineKeyboardButton(text="👥 Join Group", url=f"https://t.me/{GROUP.replace('@','')}")
        ],
        [
            InlineKeyboardButton(text="🔄 Cek Join", callback_data="cek_join")
        ]
    ])


# =========================
# CHECK JOIN
# =========================
async def check_join(bot, user_id: int, chat: str):
    try:
        member = await bot.get_chat_member(chat, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


# =========================
# SAVE USER (AUTO)
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
# START
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user

    # SAVE USER FOR BROADCAST
    await save_user(user)

    # FORCE JOIN CHECK (ANTI BYPASS)
    ch = await check_join(bot, user.id, CHANNEL)
    gp = await check_join(bot, user.id, GROUP)

    if not ch or not gp:
        await message.answer(
            "⚠️ Kamu harus join channel & group untuk menggunakan bot:",
            reply_markup=join_kb()
        )
        return

    # BALANCE DEFAULT (NANTI CONNECT DB)
    balance = 0

    await message.answer(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )


# =========================
# CEK JOIN BUTTON
# =========================
@router.callback_query(F.data == "cek_join")
async def cek_join(callback: CallbackQuery, bot):
    user_id = callback.from_user.id

    ch = await check_join(bot, user_id, CHANNEL)
    gp = await check_join(bot, user_id, GROUP)

    if ch and gp:
        await callback.message.edit_text(
            "✅ Join berhasil!\n\nMasuk ke bot...",
            reply_markup=home_kb()
        )
    else:
        await callback.answer("❌ Kamu belum join semua", show_alert=True)


# =========================
# HOME REFRESH
# =========================
@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    user = callback.from_user

    balance = 0  # nanti dari DB / webhook

    await callback.message.edit_text(
        dashboard_text(user, balance),
        reply_markup=home_kb(),
        parse_mode="HTML"
    )
    await callback.answer()
