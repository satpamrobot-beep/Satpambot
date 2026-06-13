from aiogram import Bot
import os
from bot.db.database import get_pool

# =========================
# BOT INSTANCE
# =========================
bot: Bot | None = None


def set_bot(instance: Bot):
    global bot
    bot = instance


# =========================
# CONFIG
# =========================
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))


# =========================
# BASE SEND SAFE
# =========================
async def send_group(text: str):
    if not bot or not ADMIN_GROUP_ID:
        return

    try:
        await bot.send_message(
            ADMIN_GROUP_ID,
            text,
            parse_mode="HTML"
        )
    except:
        pass


async def send_user(user_id: int, text: str):
    if not bot:
        return

    try:
        await bot.send_message(
            user_id,
            text,
            parse_mode="HTML"
        )
    except:
        pass


# =========================
# PAYMENT NOTIFY
# =========================
async def notify_payment(user_id: int, amount: int, trx_id: str = ""):
    await send_group(
        "💸 <b>PAYMENT SUCCESS</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Amount: Rp {amount:,.0f}\n"
        f"TRX: <code>{trx_id}</code>"
    )

    await send_user(
        user_id,
        f"💰 Saldo masuk Rp {amount:,.0f}"
    )


# =========================
# WITHDRAW NOTIFY
# =========================
async def notify_withdraw(wd_id: int, user_id: int, amount: int, status: str):
    await send_group(
        "💸 <b>WITHDRAW</b>\n"
        f"WD: {wd_id}\n"
        f"User: <code>{user_id}</code>\n"
        f"Amount: Rp {amount:,.0f}\n"
        f"Status: {status}"
    )

    await send_user(
        user_id,
        f"Withdraw {status}: Rp {amount:,.0f}"
    )


# =========================
# CODE CREATED
# =========================
async def notify_code_created(user_id: int, code: str, price: int):
    await send_group(
        "🔑 <b>NEW CODE</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Code: <code>{code}</code>\n"
        f"Price: Rp {price:,.0f}"
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
