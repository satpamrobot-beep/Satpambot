from aiogram import Bot
import os
import asyncio

from bot.db.database import get_pool

bot: Bot | None = None


def set_bot(instance: Bot):
    global bot
    bot = instance


ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))


# =========================
# SEND SAFE USER MESSAGE
# =========================
async def send_user(user_id: int, text: str):
    if not bot:
        return
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except:
        pass


# =========================
# SEND ADMIN GROUP LOG
# =========================
async def send_group(text: str):
    if not bot or not ADMIN_GROUP_ID:
        return
    try:
        await bot.send_message(ADMIN_GROUP_ID, text, parse_mode="HTML")
    except:
        pass


# =========================
# PAYMENT NOTIFY (USER + ADMIN)
# =========================
async def notify_payment(user_id: int, amount: int, trx_id: str):
    await send_user(
        user_id,
        f"💰 <b>Payment Success</b>\n"
        f"Saldo masuk: Rp {amount:,.0f}\n"
        f"TRX: {trx_id}"
    )

    await send_group(
        "💸 <b>PAYMENT SUCCESS</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Amount: Rp {amount:,.0f}\n"
        f"TRX: <code>{trx_id}</code>"
    )


# =========================
# WITHDRAW NOTIFY
# =========================
async def notify_withdraw(user_id: int, amount: int, status: str):
    await send_user(
        user_id,
        f"💸 Withdraw {status}\nRp {amount:,.0f}"
    )

    await send_group(
        f"💸 WD {status}\nUser: {user_id}\nAmount: {amount}"
    )


# =========================
# BROADCAST ALL USERS
# =========================
async def broadcast(text: str):
    if not bot:
        return

    pool = get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")

    for u in users:
        try:
            await bot.send_message(u["user_id"], text)
        except:
            pass
