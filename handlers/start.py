import asyncio

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject
from aiogram.exceptions import TelegramBadRequest

from db.users import add_user, get_user_balance
from services.join import is_joined

router = Router()


# ================= DASHBOARD =================
def dashboard_text(user, balance_rp: int):
    username = f"@{user.username}" if user.username else "Hidden"
    usd = balance_rp / 16000

    return (
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        "┃ 💰 <b>EARN FILE BOT</b> ┃\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        f"👤 User : {username}\n"
        f"🆔 ID   : <code>{user.id}</code>\n"
        f"💳 Balance : Rp {balance_rp:,.0f}  •  $ {usd:.2f}\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🚀 Upload • Share • Earn"
    )


# ================= START FIX DEEP LINK =================
@router.message(CommandStart(deep_link=True))
async def start(message: Message, command: CommandObject):
    user = message.from_user
    payload = command.args  # <-- isi dari ?start=xxxxx

    try:
        await add_user(user.id, user.username, user.first_name)
    except:
        pass

    if not await is_joined(message.bot, user.id):
        return await message.answer("⚠️ Join dulu sebelum lanjut.")

    balance = await get_user_balance(user.id)

    # ================= GETFILE MODE =================
    if payload:
        code = payload.replace("decodefilebot_", "")

        return await message.answer(
            "📥 GET FILE\n\n"
            f"🔑 CODE: <code>{code}</code>\n"
            "⏳ Loading file...",
            parse_mode="HTML"
        )

    # ================= NORMAL DASHBOARD =================
    await message.answer(
        dashboard_text(user, balance)
    )
