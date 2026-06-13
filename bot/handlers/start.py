import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated

from bot.state.admin_state import is_maintenance
from bot.db.database import get_pool
from bot.db.user import save_user

router = Router()

# =========================
# CONFIG
# =========================
CHANNEL = -1004395938795


# =========================
# UI
# =========================
def dashboard_text(user, balance: int):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance / 16000

    return (
        "📱 <b>APP DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"👤 User: {username}\n"
        f"🆔 ID: <code>{user.id}</code>\n\n"
        f"💰 Balance: Rp {balance:,.0f}\n"
        f"💵 USD: $ {usd:.2f}\n\n"
        "━━━━━━━━━━━━━━"
    )


# =========================
# FULL MENU
# =========================
def app_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Upmedia", callback_data="upmedia"),
            InlineKeyboardButton(text="📥 Getmedia", callback_data="getmedia"),
        ],
        [
            InlineKeyboardButton(text="👤 Account", callback_data="account"),
            InlineKeyboardButton(text="💰 Withdraw", callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton(text="📦 Product", callback_data="product"),
            InlineKeyboardButton(text="💳 Wallet", callback_data="wallet"),
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
        ]
    ])
# =========================
# JOIN SCREEN
# =========================
def join_screen():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📢 Join Channel",
                url="https://t.me/+mp7HeZPteus0ZDQ9"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Check Access",
                callback_data="check_access"
            )
        ]
    ])


# =========================
# DB
# =========================
async def get_balance(user_id: int):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT balance FROM users WHERE user_id=$1",
                user_id
            ) or 0
    except:
        return 0


# =========================
# JOIN CHECK (ANTI BYPASS FIX)
# =========================
async def is_joined(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        status = member.status

        # HARD BLOCK RULE
        if status in ("left", "kicked"):
            return False

        return status in ("member", "administrator", "creator")

    except:
        return False


# =========================
# SAFE RENDER ENGINE (NO DUPLICATE MESSAGE / NO SPAM)
# =========================
async def render(target, bot, user):

    # maintenance mode
    if is_maintenance():
        text = "⚙️ Maintenance Mode"

        try:
            if hasattr(target, "message"):
                await target.message.edit_text(text)
            else:
                await target.answer(text)
        except:
            pass
        return

    # JOIN GATE
    if not await is_joined(bot, user.id):

        text = "🚫 Akses ditolak\nSilakan join channel dulu"

        try:
            if hasattr(target, "message"):
                await target.message.edit_text(text, reply_markup=join_screen())
            else:
                await target.answer(text, reply_markup=join_screen())
        except:
            if hasattr(target, "message"):
                await target.message.answer(text, reply_markup=join_screen())
        return

    # DASHBOARD
    balance = await get_balance(user.id)
    text = dashboard_text(user, balance)

    try:
        if hasattr(target, "message"):
            await target.message.edit_text(
                text,
                reply_markup=app_menu(),
                parse_mode="HTML"
            )
        else:
            await target.answer(
                text,
                reply_markup=app_menu(),
                parse_mode="HTML"
            )
    except:
        if hasattr(target, "message"):
            await target.message.answer(
                text,
                reply_markup=app_menu(),
                parse_mode="HTML"
            )


# =========================
# START
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):

    user = message.from_user

    asyncio.create_task(save_user(user))

    await render(message, bot, user)


# =========================
# GLOBAL CALLBACK ROUTER
# =========================
@router.callback_query(
    F.data.in_({
        "account",
        "withdraw",
        "product",
        "wallet",
        "help",
        "about",
    })
)
async def router_all(callback: CallbackQuery, bot):

    await render(callback, bot, callback.from_user)
    await callback.answer()
# =========================
# REALTIME DETECTOR (AUTO LOCK)
# =========================
@router.chat_member()
async def on_chat_member(update: ChatMemberUpdated, bot):

    user_id = update.from_user.id
    status = update.new_chat_member.status

    # kalau keluar channel → lock access
    if status in ("left", "kicked"):

        try:
            await bot.send_message(
                user_id,
                "🚫 Kamu keluar dari channel\nAkses aplikasi dikunci."
            )
        except:
            pass
