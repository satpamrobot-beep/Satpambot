import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.state.admin_state import is_maintenance
from bot.db.database import get_pool
from bot.db.user import save_user

router = Router()


# =========================
# UI
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
# KEYBOARD (NO REFRESH)
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
# SAFE DASHBOARD SENDER (AUTO UPDATE CORE)
# =========================
async def send_dashboard(message_or_callback, user):
    balance = await get_balance(user.id)

    text = dashboard_text(user, balance)

    if hasattr(message_or_callback, "message"):
        # callback
        msg = message_or_callback.message

        try:
            await msg.edit_text(
                text,
                reply_markup=home_kb(),
                parse_mode="HTML"
            )
        except:
            await msg.answer(
                text,
                reply_markup=home_kb(),
                parse_mode="HTML"
            )
    else:
        # message
        await message_or_callback.answer(
            text,
            reply_markup=home_kb(),
            parse_mode="HTML"
        )


# =========================
# START
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):

    user = message.from_user

    if is_maintenance():
        await message.answer("⚙️ Bot sedang maintenance")
        return

    asyncio.create_task(save_user(user))

    await send_dashboard(message, user)


# =========================
# AUTO UPDATE ALL CALLBACKS
# =========================
@router.callback_query()
async def menu_router(callback: CallbackQuery):

    user = callback.from_user

    if is_maintenance():
        await callback.answer("⚙️ Maintenance", show_alert=True)
        return

    await send_dashboard(callback, user)
    await callback.answer()
