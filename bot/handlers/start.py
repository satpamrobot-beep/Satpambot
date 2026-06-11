from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart

from db.users import ensure_user, get_balance

router = Router()

# =========================
# CONFIG
# =========================
ADMIN_IDS = [6847035364]

CHANNEL_ID = -1003712587847
GROUP_ID = -1003920865154


# =========================
# FORCE JOIN KB
# =========================
def force_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Channel Update", url="https://t.me/yourchannel")],
        [InlineKeyboardButton(text="💬 Group Chat", url="https://t.me/yourgroup")],
        [InlineKeyboardButton(text="✅ Done Cek", callback_data="check_join")]
    ])


# =========================
# DASHBOARD KB
# =========================
def dashboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 UpFile", callback_data="upfile"),
            InlineKeyboardButton(text="📥 GetFile", callback_data="getfile"),
        ],
        [
            InlineKeyboardButton(text="👤 Account", callback_data="account"),
            InlineKeyboardButton(text="💳 Withdraw", callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Setting", callback_data="setting"),
            InlineKeyboardButton(text="📊 Statistik", callback_data="statistik"),
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
        ],
    ])


# =========================
# JOIN CHECK (SAFE)
# =========================
async def is_joined(bot, user_id: int) -> bool:
    try:
        ch = await bot.get_chat_member(CHANNEL_ID, user_id)
        gr = await bot.get_chat_member(GROUP_ID, user_id)

        return ch.status in ("member", "administrator", "creator") and \
               gr.status in ("member", "administrator", "creator")
    except:
        return False


# =========================
# FORMAT DASHBOARD
# =========================
def format_dashboard(user, idr, usd):
    username = f"@{user.username}" if user.username else "-"

    return (
        "🐧 <b>Bluebird Code Earn</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID Account : <code>{user.id}</code>\n"
        f"📛 Username   : {username}\n"
        f"🧾 Name       : {user.full_name}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💰 Saldo      : Rp {idr:,} / ${usd:.2f}\n"
        "━━━━━━━━━━━━━━━━━━"
    )


# =========================
# START COMMAND (FAST MODE)
# =========================
@router.message(CommandStart())
async def start(message: Message):
    bot = message.bot
    user = message.from_user

    # ⚡ prevent duplicate heavy DB load
    try:
        await ensure_user(user.id, user.username, user.full_name)
    except:
        pass

    # ⚡ FORCE JOIN FIRST
    if not await is_joined(bot, user.id):
        await message.answer(
            "⚠️ Join dulu untuk lanjut pakai bot.",
            reply_markup=force_join_kb()
        )
        return

    # ⚡ GET WALLET
    idr, usd = await get_balance(user.id)

    await message.answer(
        format_dashboard(user, idr, usd),
        reply_markup=dashboard_kb()
    )

    # =========================
    # ADMIN DETECT (SAFE)
    # =========================
    if user.id in ADMIN_IDS:
        await message.answer(
            "👑 Admin detected",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Open Admin Panel",
                    callback_data="admin_panel"
                )]
            ])
        )


# =========================
# CHECK JOIN CALLBACK
# =========================
@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    bot = call.bot
    user = call.from_user

    try:
        await ensure_user(user.id, user.username, user.full_name)
    except:
        pass

    if await is_joined(bot, user.id):

        try:
            await call.message.delete()
        except:
            pass

        idr, usd = await get_balance(user.id)

        await call.message.answer(
            format_dashboard(user, idr, usd),
            reply_markup=dashboard_kb()
        )

    else:
        await call.answer("❌ Kamu belum join semua channel/group", show_alert=True)
