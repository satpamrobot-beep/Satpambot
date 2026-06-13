import asyncio
import time

from bot.db.user import save_user
from aiogram import Router, F
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMemberUpdated
)

from bot.state.admin_state import is_maintenance
from bot.db.database import get_pool

router = Router()

# =========================
# CONFIG
# =========================
CHANNEL = -1003777107004
GROUP = -1003721009353

# =========================
# CACHE
# =========================
JOIN_CACHE = {}
CACHE_TTL = 60


def cache_get(user_id: int, chat_id: int):
    key = (user_id, chat_id)
    data = JOIN_CACHE.get(key)

    if not data:
        return None

    status, exp = data
    if time.time() > exp:
        JOIN_CACHE.pop(key, None)
        return None

    return status


def cache_set(user_id: int, chat_id: int, status: bool):
    JOIN_CACHE[(user_id, chat_id)] = (status, time.time() + CACHE_TTL)


def cache_clear_user(user_id: int):
    for k in list(JOIN_CACHE.keys()):
        if k[0] == user_id:
            JOIN_CACHE.pop(k, None)


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
        [InlineKeyboardButton(text="ℹ️ About", callback_data="about")],
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="home")]
    ])


def join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/+OzP85qRqCUhjMDE1")],
        [InlineKeyboardButton(text="👥 Join Group", url="https://t.me/+DTL9cOR34ipmM2U1")],
        [InlineKeyboardButton(text="🔄 Check Join", callback_data="cek_join")]
    ])


# =========================
# CHECK JOIN CORE (FAST + CACHE)
# =========================
async def check_join(bot, user_id: int, chat: int) -> bool:
    cached = cache_get(user_id, chat)
    if cached is not None:
        return cached

    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
        status = member.status

        ok = status in ("member", "administrator", "creator")

        cache_set(user_id, chat, ok)

        print(f"[JOIN CHECK] user={user_id} chat={chat} status={status} ok={ok}")

        return ok

    except Exception as e:
        print("[JOIN ERROR]", e)
        return False


async def force_join(bot, user_id: int) -> bool:
    ch, gp = await asyncio.gather(
        check_join(bot, user_id, CHANNEL),
        check_join(bot, user_id, GROUP)
    )
    return ch and gp


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
# CHECK JOIN BUTTON
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

    await callback.answer()


# =========================
# REAL-TIME JOIN DETECTOR + AUTO BAN
# =========================
@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=True))
async def on_chat_member(update: ChatMemberUpdated, bot):

    user_id = update.from_user.id
    new_status = update.new_chat_member.status

    print(f"[CHAT MEMBER UPDATE] user={user_id} status={new_status}")

    # kalau keluar / kick
    if new_status in ("left", "kicked"):

        cache_clear_user(user_id)

        # AUTO BAN (pastikan bot admin di channel & group)
        try:
            await bot.ban_chat_member(CHANNEL, user_id)
        except Exception as e:
            print("[BAN CHANNEL ERROR]", e)

        try:
            await bot.ban_chat_member(GROUP, user_id)
        except Exception as e:
            print("[BAN GROUP ERROR]", e)

        print(f"[AUTO BAN EXECUTED] user={user_id}")
