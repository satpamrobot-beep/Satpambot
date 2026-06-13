import asyncio
import time
from collections import defaultdict

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton

from bot.state.admin_state import is_maintenance
from bot.db.database import get_pool

router = Router()

# =========================
# CONFIG
# =========================
CHANNEL = -1003777107004
GROUP = -1003721009353

# =========================
# CACHE JOIN (FAST)
# =========================
JOIN_CACHE = {}
CACHE_TTL = 30

# =========================
# ANTI FAKE / MULTI ACCOUNT DETECTION
# =========================
USER_JOIN_LOG = defaultdict(list)  # user_id -> timestamps
SUSPICIOUS_USERS = set()

JOIN_LIMIT_WINDOW = 60  # detik
JOIN_LIMIT_MAX = 5      # max join/leave event dalam window


# =========================
# CACHE
# =========================
def cache_get(key):
    data = JOIN_CACHE.get(key)
    if not data:
        return None

    val, exp = data
    if time.time() > exp:
        JOIN_CACHE.pop(key, None)
        return None

    return val


def cache_set(key, val):
    JOIN_CACHE[key] = (val, time.time() + CACHE_TTL)


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
        [InlineKeyboardButton(text="📢 Join Channel", url="https://t.me/+pGH77U2t6_45NTU1")],
        [InlineKeyboardButton(text="👥 Join Group", url="https://t.me/+DTL9cOR34ipmM2U1")],
        [InlineKeyboardButton(text="🔄 Check Join", callback_data="cek_join")]
    ])


# =========================
# CORE CHECK (NO BYPASS)
# =========================
async def check_join(bot, user_id: int, chat: int) -> bool:
    try:
        member = await bot.get_chat_member(chat, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


async def force_join(bot, user_id: int) -> bool:
    ch, gp = await asyncio.gather(
        check_join(bot, user_id, CHANNEL),
        check_join(bot, user_id, GROUP)
    )
    return ch and gp


# =========================
# ANTI FAKE JOIN TRACKER
# =========================
def track_join_activity(user_id: int):
    now = time.time()
    USER_JOIN_LOG[user_id].append(now)

    # keep last 1 minute only
    USER_JOIN_LOG[user_id] = [
        t for t in USER_JOIN_LOG[user_id]
        if now - t <= JOIN_LIMIT_WINDOW
    ]

    if len(USER_JOIN_LOG[user_id]) >= JOIN_LIMIT_MAX:
        SUSPICIOUS_USERS.add(user_id)
        return False

    return True


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
# START (HARD GATE)
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):

    user = message.from_user

    if is_maintenance():
        await message.answer("⚙️ Maintenance")
        return

    # 🔥 ANTI FAKE / MULTI ACCOUNT CHECK
    if not track_join_activity(user.id):
        await message.answer("🚫 Suspicious activity detected")
        return

    # 🔥 HARD JOIN CHECK (NO CACHE TRUST)
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
# REALTIME DETECTOR + AUTO BAN
# =========================
@router.chat_member()
async def on_chat_member(update: ChatMemberUpdated, bot):

    user_id = update.from_user.id
    status = update.new_chat_member.status
    chat_id = update.chat.id

    print(f"[REALTIME] user={user_id} chat={chat_id} status={status}")

    # 🔥 DETECT LEAVE / KICK
    if status in ("left", "kicked"):

        track_join_activity(user_id)

        try:
            await bot.ban_chat_member(chat_id, user_id)
        except:
            pass

        print(f"[AUTO BAN] {user_id}")

    # 🔥 DETECT JOIN SPAM (FAKE JOIN PATTERN)
    if status == "member" and user_id in SUSPICIOUS_USERS:

        try:
            await bot.ban_chat_member(chat_id, user_id)
        except:
            pass

        print(f"[ANTI FAKE JOIN BAN] {user_id}")
