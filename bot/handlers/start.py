import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.state.admin_state import is_maintenance
from bot.db.database import get_pool
from bot.db.user import save_user

router = Router()

# =========================
# CONFIG (ONLY 1 CHANNEL)
# =========================
CHANNEL = -1004395938795

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
        ]
    ])


# =========================
# JOIN BUTTON (ONLY 1)
# =========================
def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📢 Channel Update Link",
                url="https://t.me/+mp7HeZPteus0ZDQ9"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Check Join",
                callback_data="check_join"
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
# FORCE CHECK (ANTI BYPASS CORE)
# =========================
async def is_joined(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


# =========================
# DASHBOARD SENDER (AUTO GATE)
# =========================
async def send_dashboard(target, bot, user):

    if not await is_joined(bot, user.id):
        await target.answer(
            "⚠️ Kamu harus join Channel dulu",
            reply_markup=join_kb()
        )
        return

    balance = await get_balance(user.id)

    await target.answer(
        dashboard_text(user, balance),
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

    await send_dashboard(message, bot, user)


# =========================
# CHECK JOIN BUTTON
# =========================
@router.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery, bot):

    user = callback.from_user

    if await is_joined(bot, user.id):
        await callback.message.edit_text(
            "✅ Join verified, loading dashboard..."
        )

        await send_dashboard(callback.message, bot, user)
        await callback.answer()

    else:
        await callback.answer("❌ Kamu belum join channel", show_alert=True)


# =========================
# AUTO BLOCK IF LEFT (REALTIME SAFE)
# =========================
@router.chat_member()
async def on_chat_member(update, bot):

    user_id = update.from_user.id
    new_status = update.new_chat_member.status

    # kalau keluar
    if new_status in ("left", "kicked"):
        print(f"[LEFT DETECTED] {user_id}")
