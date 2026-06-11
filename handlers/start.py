from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from db.users import ensure_user, get_balance
from bot.services.join import is_joined
from bot.keyboards.user import dashboard_kb, force_join_kb

router = Router()

ADMIN_IDS = [6847035364]


def format_dashboard(user, idr, usd):
    return (
        "🐧 <b>Bluebird CodeEarn</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{user.id}</code>\n"
        f"📛 Name: {user.full_name}\n"
        f"💰 Wallet: Rp {idr:,} / ${usd}\n"
        "━━━━━━━━━━━━━━"
    )


@router.message(CommandStart())
async def start(message: Message):
    bot = message.bot
    user = message.from_user

    await ensure_user(user.id, user.username, user.full_name)

    if not await is_joined(bot, user.id):
        await message.answer("⚠️ Join dulu", reply_markup=force_join_kb())
        return

    idr, usd = await get_balance(user.id)

    await message.answer(
        format_dashboard(user, idr, usd),
        reply_markup=dashboard_kb()
    )

    if user.id in ADMIN_IDS:
        await message.answer(
            "👑 Admin detected",
            reply_markup=dashboard_kb()
        )
