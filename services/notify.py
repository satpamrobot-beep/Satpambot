import os
import asyncio
from aiogram import Bot

from bot.db.database import get_pool
from bot.state.admin_state import is_maintenance

# =========================
# BOT INSTANCE
# =========================
bot: Bot | None = None


def set_bot(instance: Bot):
    global bot
    bot = instance


# =========================
# ENV CONFIG
# =========================
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))


# =========================
# SAFE USER MESSAGE
# =========================
async def send_user(user_id: int, text: str):
    if not bot:
        return

    # 🔴 BLOCK USER JIKA MAINTENANCE
    if is_maintenance():
        try:
            await bot.send_message(
                user_id,
                "⚙️ Bot sedang maintenance\nSilakan coba lagi nanti"
            )
        except:
            pass
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
# GROUP LOG (ADMIN LOG)
# =========================
async def send_group(text: str):
    if not bot or ADMIN_GROUP_ID == 0:
        return

    try:
        await bot.send_message(
            ADMIN_GROUP_ID,
            f"📢 <b>ADMIN LOG</b>\n\n{text}",
            parse_mode="HTML"
        )
    except:
        pass


# =========================
# PAYMENT NOTIFY
# =========================
async def notify_payment(user_id: int, amount: int, trx_id: str):
    await send_user(
        user_id,
        f"💰 <b>Payment Success</b>\n"
        f"Saldo masuk: <b>Rp {amount:,.0f}</b>\n"
        f"TRX: <code>{trx_id}</code>"
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
        f"💸 <b>Withdraw {status}</b>\n"
        f"Amount: Rp {amount:,.0f}"
    )

    await send_group(
        f"💸 <b>WITHDRAW {status}</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Amount: Rp {amount:,.0f}"
    )


# =========================
# BROADCAST ALL USERS
# =========================
async def broadcast(text: str):
    if not bot:
        return

    # 🔴 BLOCK BROADCAST IF MAINTENANCE
    if is_maintenance():
        return

    pool = get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM users")

    for u in users:
        try:
            await bot.send_message(
                u["user_id"],
                text,
                parse_mode="HTML"
            )
            await asyncio.sleep(0.03)  # anti flood Telegram
        except:
            continue


# =========================
# CODE CREATED NOTIFY (IMPORTANT FEATURE)
# =========================
async def notify_new_code(user_id: int, code: str, price: int):
    """
    dipakai saat user generate / buy code
    """

    await send_user(
        user_id,
        "📦 <b>Code Created</b>\n"
        f"🔑 Code: <code>{code}</code>\n"
        f"💰 Price: Rp {price:,.0f}"
    )

    await send_group(
        "📦 <b>NEW CODE CREATED</b>\n"
        f"User: <code>{user_id}</code>\n"
        f"Code: <code>{code}</code>\n"
        f"Price: Rp {price:,.0f}"
    )


# =========================
# SAFE WRAPPER (ANTI ERROR SYSTEM)
# =========================
async def safe_send(func, *args):
    try:
        await func(*args)
    except:
        pass
