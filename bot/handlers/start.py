from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart

from db.users import ensure_user, get_balance

router = Router()

CHANNEL_ID = -1003712587847
GROUP_ID = -1003920865154


def force_join_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Channel Update", url="https://t.me/+3g_yhHwxCrc5ZTg9")],
        [InlineKeyboardButton(text="💬 Group Chat", url="https://t.me/+1tipdp-NTywzODhl")],
        [InlineKeyboardButton(text="✅ Done Cek", callback_data="check_join")]
    ])


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


async def is_joined(bot, user_id: int) -> bool:
    try:
        ch = await bot.get_chat_member(CHANNEL_ID, user_id)
        gr = await bot.get_chat_member(GROUP_ID, user_id)

        return ch.status in ["member", "administrator", "creator"] and \
               gr.status in ["member", "administrator", "creator"]
    except:
        return False


@router.message(CommandStart())
async def start_cmd(message: Message):
    bot = message.bot
    user = message.from_user

    await ensure_user(user.id, user.username, user.full_name)

    if not await is_joined(bot, user.id):
        await message.answer(
            "⚠️ Join dulu bro biar bisa lanjut.",
            reply_markup=force_join_kb()
        )
        return

    idr, usd = await get_balance(user.id)

    text = (
        f"👋 Hay {user.full_name}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"💰 Saldo: Rp {idr:,} / ${usd}\n"
    )

    await message.answer(text, reply_markup=dashboard_kb())


@router.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    bot = call.bot
    user = call.from_user

    if await is_joined(bot, user.id):

        await call.message.delete()

        idr, usd = await get_balance(user.id)

        text = (
            f"👋 Hay {user.full_name}\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"💰 Saldo: Rp {idr:,} / ${usd}\n"
        )

        await call.message.answer(text, reply_markup=dashboard_kb())

    else:
        await call.answer("❌ Belum join semua", show_alert=True)
