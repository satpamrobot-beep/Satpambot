from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart

from db.pool import get_user

router = Router()

CHANNEL_ID = -1003712587847
GROUP_ID = -1003920865154


# =========================
# FORCE JOIN BUTTON
# =========================
def force_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 Channel Update", url="https://t.me/yourchannel"),
        ],
        [
            InlineKeyboardButton(text="💬 Group Chat", url="https://t.me/yourgroup"),
        ],
        [
            InlineKeyboardButton(text="✅ Done Cek", callback_data="check_join")
        ]
    ])


# =========================
# DASHBOARD BUTTON
# =========================
def dashboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 UpFile", callback_data="upfile"),
            InlineKeyboardButton(text="📥 GetFile", callback_data="getfile"),
        ],
        [
            InlineKeyboardButton(text="👤 Account", callback_data="account"),
            InlineKeyboardButton(text="💳 Payment", callback_data="payment"),
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
        ],
    ])


# =========================
# CHECK JOIN FUNCTION
# =========================
async def is_joined(bot, user_id: int) -> bool:
    try:
        ch = await bot.get_chat_member(CHANNEL_ID, user_id)
        gr = await bot.get_chat_member(GROUP_ID, user_id)

        return ch.status in ["member", "administrator", "creator"] and \
               gr.status in ["member", "administrator", "creator"]
    except:
        return False


# =========================
# FORMAT DASHBOARD
# =========================
def format_dashboard(user, db_user):
    idr = int(db_user.get("balance_idr", 0))
    usd = float(db_user.get("balance_usd", 0))

    return (
        f"👋 Hay {user.full_name}\n"
        f"🆔 Id : <code>{user.id}</code>\n"
        f"💰 Saldo : Rp {idr:,} / $ {usd:.2f}\n\n"
        f"🔥 Dashboard Active"
    )


# =========================
# START COMMAND
# =========================
@router.message(CommandStart())
async def start_cmd(message: Message):
    bot = message.bot
    user = message.from_user

    # FORCE JOIN CHECK
    if not await is_joined(bot, user.id):
        await message.answer(
            "⚠️ Join terlebih dahulu untuk memastikan kamu bukan bot.",
            reply_markup=force_join_kb()
        )
        return

    # GET / CREATE USER (REAL DB)
    db_user = await get_user(user.id, user.full_name)

    await message.answer(
        format_dashboard(user, db_user),
        reply_markup=dashboard_kb()
    )


# =========================
# CHECK JOIN CALLBACK
# =========================
@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    bot = call.bot
    user = call.from_user

    if await is_joined(bot, user.id):

        # hapus pesan force join
        try:
            await call.message.delete()
        except:
            pass

        db_user = await get_user(user.id, user.full_name)

        await call.message.answer(
            format_dashboard(user, db_user),
            reply_markup=dashboard_kb()
        )

    else:
        await call.answer(
            "❌ Kamu belum join semua channel/group",
            show_alert=True
        )
