from aiogram import Bot
import os

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
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # optional


# =========================
# BASE SENDER (SAFE)
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
    text = (
        "💸 <b>PAYMENT SUCCESS</b>\n"
        "──────────────\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"💰 Amount: Rp {amount:,.0f}\n"
        f"🧾 TRX: <code>{trx_id}</code>\n"
    )

    await send_group(text)

    await send_user(
        user_id,
        "💰 <b>Saldo Masuk</b>\n\n"
        f"Rp {amount:,.0f}\n"
        "Status: SUCCESS"
    )


# =========================
# WITHDRAW NOTIFY
# =========================
async def notify_withdraw(wd_id: int, user_id: int, amount: int, status: str):
    text = (
        "💸 <b>WITHDRAW UPDATE</b>\n"
        "──────────────\n"
        f"🆔 WD: <code>{wd_id}</code>\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"💰 Amount: Rp {amount:,.0f}\n"
        f"📌 Status: <b>{status}</b>\n"
    )

    await send_group(text)

    await send_user(
        user_id,
        f"💸 Withdraw {status}\nRp {amount:,.0f}"
    )


# =========================
# CODE CREATED NOTIFY
# =========================
async def notify_code_created(user_id: int, code: str, price: int):
    text = (
        "🔑 <b>NEW CODE CREATED</b>\n"
        "──────────────\n"
        f"👤 User: <code>{user_id}</code>\n"
        f"🔐 Code: <code>{code}</code>\n"
        f"💰 Price: Rp {price:,.0f}\n"
    )

    await send_group(text)


# =========================
# CODE SOLD NOTIFY (OPTIONAL)
# =========================
async def notify_code_sold(buyer_id: int, code: str, price: int):
    text = (
        "🛒 <b>CODE SOLD</b>\n"
        "──────────────\n"
        f"👤 Buyer: <code>{buyer_id}</code>\n"
        f"🔐 Code: <code>{code}</code>\n"
        f"💰 Price: Rp {price:,.0f}\n"
    )

    await send_group(text)


# =========================
# GENERAL EVENT LOG
# =========================
async def send_event(title: str, message: str):
    text = (
        f"📌 <b>{title}</b>\n"
        "──────────────\n"
        f"{message}"
    )

    await send_group(text)
