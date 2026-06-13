from aiogram import Router, F
from aiogram.types import Message

from bot.db.database import get_pool

router = Router()

# ganti ini dengan ID kamu
ADMIN_ID = 123456789


# =========================
# CHECK ADMIN
# =========================
def is_admin(user_id: int):
    return user_id == ADMIN_ID


# =========================
# /admin PANEL
# =========================
@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("❌ Access denied")

    pool = get_pool()

    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        total_income = await conn.fetchval("SELECT SUM(amount) FROM transactions")
        total_trx = await conn.fetchval("SELECT COUNT(*) FROM transactions")

    await message.answer(
        "🛠 <b>ADMIN PANEL</b>\n"
        "──────────────\n\n"
        f"👥 Users: <b>{total_users or 0}</b>\n"
        f"💰 Income: <b>Rp {total_income or 0:,.0f}</b>\n"
        f"📊 Transactions: <b>{total_trx or 0}</b>\n",
        parse_mode="HTML"
    )
