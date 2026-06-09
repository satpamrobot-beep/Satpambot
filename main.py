# =========================
# IMPORT
# =========================

import os
import re
import secrets
import string
import asyncpg
import time
import asyncio
import random
import hashlib
import hmac
import uvicorn
import httpx

from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, HTTPException
from collections import defaultdict
from dotenv import load_dotenv
from aiogram.filters import CommandStart
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument
)

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

# =========================
# TIMEZONE (GLOBAL)
# =========================

WIB = timezone(timedelta(hours=7))

def now_wib():
    return datetime.now(WIB)

# =========================
# WITHDRAW STATUS LOGIC
# =========================

def wd_status():
    now = now_wib()
    weekday = now.weekday()
    hour = now.hour

    OPEN = 9
    CLOSE = 20

    # weekend (Sabtu-Minggu)
    if weekday >= 5:
        days_to_monday = 7 - weekday
        next_open = (now + timedelta(days=days_to_monday)).replace(hour=OPEN, minute=0, second=0)
        diff = next_open - now

        return False, next_open, f"⛔ WEEKEND CLOSED\n🕘 Buka lagi dalam {diff.days} hari {diff.seconds//3600} jam"

    # before open
    if hour < OPEN:
        next_open = now.replace(hour=OPEN, minute=0, second=0)
        diff = next_open - now
        return False, next_open, f"⏳ Akan buka dalam {diff.seconds//3600} jam {diff.seconds%3600//60} menit"

    # after close
    if hour >= CLOSE:
        next_open = (now + timedelta(days=1)).replace(hour=OPEN, minute=0, second=0)

        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        diff = next_open - now
        return False, next_open, f"⛔ CLOSED\n🕘 Buka lagi dalam {diff.seconds//3600} jam {diff.seconds%3600//60} menit"

    # OPEN
    close_time = now.replace(hour=CLOSE, minute=0, second=0)
    diff = close_time - now

    return True, close_time, f"🟢 OPEN\n⏳ Tutup dalam {diff.seconds//3600} jam {diff.seconds%3600//60} menit"

# =========================
# CONFIG
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

CHANNEL_DB = os.getenv("CHANNEL_DB")

ADMINS = set(
    int(x)
    for x in os.getenv("ADMINS", "").split(",")
    if x.strip().isdigit()
)

FORCE_CHANNEL = int(os.getenv("FORCE_CHANNEL", "-1003712587847"))
FORCE_CHANNEL_LINK = os.getenv(
    "FORCE_CHANNEL_LINK",
    "https://t.me/+3g_yhHwxCrc5ZTg9"
)
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL")
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL"))
VIP_LINK = os.getenv("VIP_LINK")
BAYARGG_API_URL = "https://www.bayar.gg/api/create-payment.php"  # contoh
BAYARGG_API_KEY = os.getenv("BAYARGG_API_KEY")

# ====================
# DB POOL
# ====================
async def init_db():
    global db_pool
    db_pool = None

    db_pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=5,
        statement_cache_size=0,
        command_timeout=15
    )

    async with db_pool.acquire() as conn:
        await conn.execute("""
        -- =========================
        -- USERS TABLE (WALLET CORE)
        -- =========================
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            fullname TEXT,
            balance BIGINT DEFAULT 0,
            total_deposit BIGINT DEFAULT 0,
            total_withdraw BIGINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- =========================
        -- CODES TABLE (FILE SYSTEM)
        -- =========================
        CREATE TABLE IF NOT EXISTS codes(
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            owner_id BIGINT,
            total_media INT,
            total_size BIGINT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_codes_owner
        ON codes(owner_id);

        -- =========================
        -- MEDIAS TABLE
        -- =========================
        CREATE TABLE IF NOT EXISTS medias(
            id SERIAL PRIMARY KEY,
            code TEXT,
            file_id TEXT,
            file_type TEXT,
            file_size BIGINT
        );

        CREATE INDEX IF NOT EXISTS idx_medias_code
        ON medias(code);

        -- =========================
        -- DEPOSITS TABLE (PAYMENT IN)
        -- =========================
        CREATE TABLE IF NOT EXISTS deposits(
            id SERIAL PRIMARY KEY,
            invoice_id TEXT UNIQUE,
            user_id BIGINT,
            amount BIGINT,
            status TEXT DEFAULT 'pending', 
            created_at TIMESTAMP DEFAULT NOW(),
            paid_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_deposits_user
        ON deposits(user_id);

        CREATE INDEX IF NOT EXISTS idx_deposits_invoice
        ON deposits(invoice_id);

        -- =========================
        -- WITHDRAW TABLE (PAYMENT OUT)
        -- =========================
        CREATE TABLE IF NOT EXISTS withdraws(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount BIGINT,
            fee BIGINT DEFAULT 0,
            net_amount BIGINT,
            method TEXT, -- bank / dana / ovo / dll
            account_name TEXT,
            account_number TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_withdraw_user
        ON withdraws(user_id);

        -- =========================
        -- USER BANK / EWALLET
        -- =========================
        CREATE TABLE IF NOT EXISTS user_payment_methods(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            method TEXT, -- bank / dana / ovo / gopay
            account_name TEXT,
            account_number TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_payment_user
        ON user_payment_methods(user_id);
        """)
# =========================
# CACHE / MEMORY
# =========================

cooldown = {
    "global": {},
    "page": {},
}
app = FastAPI()
page_history = {}
page_cooldown = {}
user_click_lock = {}
upload_sessions = {}
user_states = {}
last_edit_time = {}
user_last_action = {}
force_cache = {}

# key = (user_id, channel)
# value = (status, expire_time)

# =========================
# ANTI BANNED SYSTEM 🔥
# =========================

GLOBAL_DELAY = 0.08
last_global_send = 0

USER_DELAY = 1.5

def user_limit(user_id):
    now = time.time()
    last = user_last_action.get(user_id, 0)

    if now - last < USER_DELAY:
        return False

    user_last_action[user_id] = now
    return True

async def global_throttle():
    global last_global_send

    now = time.time()
    diff = now - last_global_send

    if diff < GLOBAL_DELAY:
        await asyncio.sleep(GLOBAL_DELAY - diff)

    last_global_send = time.time()

async def safe_send(func, *args, **kwargs):
    for _ in range(5):
        try:
            await global_throttle()
            return await func(*args, **kwargs)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

        except TelegramBadRequest as e:
            print("BAD REQUEST:", e)
            return

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(1)

# =========================
# FASTAPI INIT (WAJIB DI ATAS)
# =========================

BAYARGG_SECRET = os.getenv("BAYARGG_SECRET", "SECRET_KAMU")

def verify_signature(data: dict, signature: str):
    required_fields = ["invoice_id", "amount", "status"]

    if not all(k in data for k in required_fields):
        return False

    raw = f"{data['invoice_id']}:{data['amount']}:{data['status']}:{BAYARGG_SECRET}"
    expected = hashlib.sha256(raw.encode()).hexdigest()

    return hmac.compare_digest(expected, signature or "")
# =========================
# ROUTER
# =========================

router = Router()

# ====================
# HELPERS (DATABASE)
# ====================

async def get_balance(user_id: int):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1",
            user_id
        )
        return row["balance"] if row else 0

# =========================
# WEBHOOK
# =========================

@app.post("/bayargg/webhook")
async def bayargg_webhook(req: Request):

    data = await req.json()

    """
    expected payload:
    {
        "invoice_id": "INV-123-5000",
        "user_id": 123,
        "amount": 5000,
        "status": "PAID",
        "signature": "xxxxx"
    }
    """

    invoice_id = data.get("invoice_id")
    user_id = data.get("user_id")
    amount = data.get("amount")
    status = data.get("status")
    signature = data.get("signature")

    # =========================
    # VERIFY SIGNATURE
    # =========================
    if not verify_signature(data, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # =========================
    # ONLY PAID
    # =========================
    if status != "PAID":
        return {"ok": False, "msg": "not paid"}

    async with db_pool.acquire() as conn:

        # =========================
        # CHECK DUPLICATE (IDEMPOTENT)
        # =========================
        existing = await conn.fetchrow(
            "SELECT status FROM deposits WHERE invoice_id=$1",
            invoice_id
        )

        if existing and existing["status"] == "success":
            return {"ok": True, "msg": "already processed"}

        # =========================
        # UPDATE DEPOSIT
        # =========================
        await conn.execute("""
        UPDATE deposits
        SET status='success', paid_at=NOW()
        WHERE invoice_id=$1
        """, invoice_id)

        # =========================
        # ADD BALANCE USER
        # =========================
        await conn.execute("""
        UPDATE users
        SET balance = balance + $1
        WHERE user_id = $2
        """, amount, user_id)

    return {"ok": True, "msg": "payment processed"}

# =========================
# DASHBOARD BUILDER
# =========================

async def build_dashboard(user_id: int, username: str):

    try:
        balance = await get_balance(user_id)
    except:
        balance = 0

    text = (
        "🔥 <b>DECODEFILEBOT</b>\n\n"
        f"👤 Username: @{username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Saldo: <b>Rp {balance:,}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 DASHBOARD MENU\n"
        "━━━━━━━━━━━━━━\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Upfile", callback_data="upfile"),
            InlineKeyboardButton(text="📥 Getfile", callback_data="getfile"),
        ],
        [
            InlineKeyboardButton(text="💳 Deposit", callback_data="deposit"),
            InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistik", callback_data="statistik"),
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
        ],
    ])

    return text, keyboard


# =========================
# START
# =========================

@router.message(F.text == "/start")
async def start(message: Message, bot: Bot):

    user = message.from_user
    user_id = user.id
    username = user.username or "No Username"

    # save user
    try:
        await add_user(user_id, username, user.full_name)
    except:
        pass

    # force sub
    if FORCE_CHANNEL:
        try:
            member = await bot.get_chat_member(FORCE_CHANNEL, user_id)

            if member.status not in ("member", "administrator", "creator"):
                return await message.answer(
                    "⚠️ AKSES DITOLAK\n\nKamu harus join channel dulu sebelum pakai bot.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
                        [InlineKeyboardButton("✅ Sudah Join", callback_data="check_sub")]
                    ])
                )
        except Exception as e:
            print("FORCE SUB EROR:", repr(e))

    text, keyboard = await build_dashboard(user_id, username)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


# =========================
# HOME CALLBACK (SAMA DENGAN START)
# =========================

@router.callback_query(F.data == "home")
async def home(call: CallbackQuery):

    user = call.from_user
    user_id = user.id
    username = user.username or "No Username"

    text, keyboard = await build_dashboard(user_id, username)

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await call.answer()

# =========================
# DEPOSIT KEYBOARD
# =========================

def deposit_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="2.000", callback_data="dep:2000"),
            InlineKeyboardButton(text="5.000", callback_data="dep:5000"),
            InlineKeyboardButton(text="10.000", callback_data="dep:10000"),
        ],
        [
            InlineKeyboardButton(text="15.000", callback_data="dep:15000"),
            InlineKeyboardButton(text="20.000", callback_data="dep:20000"),
            InlineKeyboardButton(text="50.000", callback_data="dep:50000"),
        ],
        [
            InlineKeyboardButton(text="🔙 Kembali", callback_data="home")
        ]
    ])


# =========================
# MENU DEPOSIT
# =========================

@router.callback_query(F.data == "deposit")
async def deposit_menu(call: CallbackQuery):
    await call.message.edit_text(
        "💳 <b>DEPOSIT</b>\n\nPilih nominal:",
        parse_mode="HTML",
        reply_markup=deposit_kb()
    )
    await call.answer()


# =========================
# ANTI DOUBLE INVOICE CACHE
# =========================
ACTIVE_INVOICE = {}  # user_id -> invoice_id


# =========================
# CREATE INVOICE
# =========================

async def create_bayargg_invoice(user_id: int, amount: int):

    payload = {
        "amount": amount,
        "description": f"Deposit user {user_id}",
        "payment_method": "qris",
        "callback_url": "https://satpambot-production.up.railway.app/bayargg/webhook",
        "redirect_url": "https://t.me/decodefilebot"
    }

    headers = {
        "X-API-Key": BAYARGG_API_KEY,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(BAYARGG_API_URL, json=payload, headers=headers)

    res = r.json()
    data = res.get("data") or {}

    return {
        "invoice_id": data.get("invoice_id"),
        "payment_url": data.get("payment_url"),
        "qr_url": data.get("qris_static_image_url")
    }


# =========================
# AUTO CHECK PAYMENT LOOP
# =========================

async def auto_check_payment(invoice_id: str, user_id: int, message):
    """
    auto detect payment + auto update saldo
    """

    for _ in range(30):  # ± 5 menit (30x10s)
        await asyncio.sleep(10)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT status, amount
                FROM deposits
                WHERE invoice_id=$1
            """, invoice_id)

            if not row:
                return

            if row["status"] == "success":
                await message.edit_text(
                    "✅ <b>PEMBAYARAN BERHASIL</b>\n\n"
                    f"💰 Rp {row['amount']:,} sudah masuk saldo",
                    parse_mode="HTML"
                )
                ACTIVE_INVOICE.pop(user_id, None)
                return

            if row["status"] == "expired":
                await message.edit_text("⛔ Invoice expired")
                ACTIVE_INVOICE.pop(user_id, None)
                return


# =========================
# HANDLE DEPOSIT
# =========================

@router.callback_query(F.data.startswith("dep:"))
async def deposit_nominal(call: CallbackQuery):

    user_id = call.from_user.id
    amount = int(call.data.split(":")[1])

    await call.answer("⏳ membuat invoice...")

    # =========================
    # ANTI DOUBLE INVOICE
    # =========================
    if user_id in ACTIVE_INVOICE:
        return await call.message.answer("⚠️ Kamu masih punya invoice aktif")

    try:
        inv = await create_bayargg_invoice(user_id, amount)

        invoice_id = inv["invoice_id"]
        qr_url = inv.get("qr_url")

        ACTIVE_INVOICE[user_id] = invoice_id

        msg = await call.message.edit_text(
            "💳 <b>INVOICE CREATED</b>\n\n"
            f"💰 Rp {amount:,}\n"
            f"🧾 <code>{invoice_id}</code>\n\n"
            "📌 Scan QR di bawah",
            parse_mode="HTML"
        )

        # =========================
        # QR SINGLE MESSAGE (NO SPAM)
        # =========================
        if qr_url:
            qr_msg = await call.message.answer_photo(
                qr_url,
                caption="📌 QRIS (auto delete 60 detik)"
            )

            # auto delete QR
            asyncio.create_task(delete_message(qr_msg, 60))

        # =========================
        # SAVE DB
        # =========================
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO deposits(invoice_id, user_id, amount, status)
                VALUES($1,$2,$3,'pending')
            """, invoice_id, user_id, amount)

        # =========================
        # AUTO CHECK PAYMENT
        # =========================
        asyncio.create_task(auto_check_payment(invoice_id, user_id, msg))

    except Exception as e:
        print("DEPOSIT ERROR:", repr(e))
        await call.message.edit_text("❌ Gagal membuat invoice")


# =========================
# DELETE MESSAGE HELPER
# =========================

async def delete_message(message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass


# =========================
# OPTIONAL MANUAL CHECK (BACKUP)
# =========================

@router.callback_query(F.data.startswith("checkpay:"))
async def check_payment(call: CallbackQuery):

    invoice_id = call.data.split(":")[1]

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT status, amount
            FROM deposits
            WHERE invoice_id=$1
        """, invoice_id)

    if not row:
        return await call.answer("❌ Invoice tidak ditemukan", show_alert=True)

    if row["status"] == "success":
        await call.message.edit_text(
            "✅ <b>SUDAH DIBAYAR</b>\n\n"
            f"💰 Rp {row['amount']:,}",
            parse_mode="HTML"
        )
    else:
        await call.answer("⏳ Belum dibayar", show_alert=True)

# =========================
# WITHDRAW SYSTEM FULL FINAL
# =========================

import time
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# LIMIT CONFIG
# =========================

MIN_WITHDRAW = 50000
MAX_WITHDRAW = 500000

# =========================
# BANK / EWALLET / CRYPTO LIST
# =========================

BANKS = [
    "BCA", "BRI", "BNI", "Mandiri",
    "Permata", "CIMB Niaga", "Danamon",
    "BSI", "Bank Mega",
    "Maybank Indonesia", "Public Bank MY", "CIMB Bank MY"
]

EWALLETS = [
    "DANA", "OVO", "GoPay", "ShopeePay",
    "LinkAja", "Jenius Pay",
    "TouchNGo MY", "GrabPay MY"
]

CRYPTO = [
    "Binance", "Tokocrypto", "Bitget", "Bybit", "OKX", "PayPal"
]

# =========================
# MAIN PAGE WITHDRAW
# =========================

@router.callback_query(F.data == "withdraw")
async def withdraw_page(call: CallbackQuery):

    user_id = call.from_user.id

    try:
        async with db_pool.acquire() as conn:

            # auto create user jika belum ada
            await conn.execute("""
                INSERT INTO users (user_id, balance)
                VALUES ($1, 0)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id)

            row = await conn.fetchrow("""
                SELECT balance, wd_method, wd_provider, wd_name, wd_number
                FROM users WHERE user_id=$1
            """, user_id)

        # 🔒 safety check
        if not row:
            return await call.message.edit_text("❌ User tidak ditemukan")

        balance = row["balance"] or 0

        # 🔥 pakai WD system terbaru (WIB + schedule)
        open_status, _, _ = wd_status()
        status = "🟢 OPEN" if open_status else "🔴 CLOSED"

        method = row["wd_method"] or "BELUM SET"
        provider = row["wd_provider"] or "-"
        name = row["wd_name"] or "-"
        number = row["wd_number"] or "-"

        text = (
            "💸 <b>WITHDRAW CENTER</b>\n\n"
            f"💰 Saldo Anda: <b>Rp {balance:,}".replace(",", ".") + "</b>\n"
            f"⏰ Status Sistem: <b>{status}</b>\n\n"
            "━━━━━━━━━━━━━━\n"
            "🏦 <b>DATA WITHDRAW</b>\n"
            f"• Method   : {method}\n"
            f"• Provider : {provider}\n"
            f"• Nama     : {name}\n"
            f"• Nomor    : {number}\n"
            "━━━━━━━━━━━━━━\n\n"
            f"📌 Minimal Withdraw: Rp {MIN_WITHDRAW:,}".replace(",", ".") + "\n"
            f"📌 Maksimal Withdraw: Rp {MAX_WITHDRAW:,}".replace(",", ".") + "\n\n"
            "🕘 Jadwal:\n"
            "• Senin - Jumat: 09:00 - 20:00\n"
            "• Sabtu - Minggu: TUTUP"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="💸 REQUEST WITHDRAW",
                callback_data="wd_request"
            )],
            [InlineKeyboardButton(
                text="⚙️ ATUR BANK / EWALLET",
                callback_data="wd_settings"
            )],
            [InlineKeyboardButton(
                text="🔙 KEMBALI",
                callback_data="home"
            )]
        ])

        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=kb
        )

    except Exception as e:
        print("WITHDRAW ERROR:", repr(e))
        await call.message.edit_text("❌ Gagal load withdraw")

# =========================
# STEP 1 - PILIH JENIS
# =========================

@router.callback_query(F.data == "wd_settings")
async def wd_settings(call: CallbackQuery):

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏦 BANK", callback_data="wd_type:bank"),
            InlineKeyboardButton(text="📱 EWALLET", callback_data="wd_type:ewallet"),
        ],
        [
            InlineKeyboardButton(text="₿ CRYPTO", callback_data="wd_type:crypto")
        ],
        [
            InlineKeyboardButton(text="🔙 BACK", callback_data="withdraw")
        ]
    ])

    await call.message.edit_text(
        "⚙️ <b>PILIH JENIS WITHDRAW</b>\n\n"
        "Silakan pilih metode penarikan:",
        parse_mode="HTML",
        reply_markup=kb
    )


# =========================
# STEP 2 - PILIH PROVIDER
# =========================

@router.callback_query(F.data.startswith("wd_type:"))
async def wd_type(call: CallbackQuery):

    t = call.data.split(":")[1]
    user_states[call.from_user.id] = {"type": t}

    if t == "bank":
        options = BANKS
        title = "🏦 PILIH BANK"
    elif t == "ewallet":
        options = EWALLETS
        title = "📱 PILIH EWALLET"
    else:
        options = CRYPTO
        title = "₿ PILIH CRYPTO WALLET"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=o, callback_data=f"wd_provider:{o}")]
            for o in options
        ] + [[InlineKeyboardButton(text="🔙 BACK", callback_data="wd_settings")]]
    )

    await call.message.edit_text(title, parse_mode="HTML", reply_markup=kb)


# =========================
# STEP 3 - INPUT DATA
# =========================

@router.callback_query(F.data.startswith("wd_provider:"))
async def wd_provider(call: CallbackQuery):

    user_id = call.from_user.id

    provider = call.data.split(":")[1]

    # =========================
    # SAFETY CHECK STATE
    # =========================
    if user_id not in user_states:
        user_states[user_id] = {}

    user_states[user_id]["provider"] = provider
    user_states[user_id]["mode"] = "wd_input"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔙 Kembali",
                callback_data="wd_settings"
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data="wd_cancel"
            )
        ]
    ])

    await call.message.edit_text(
        "✍️ <b>MASUKKAN DATA WITHDRAW</b>\n\n"
        f"🏦 Provider: <b>{provider}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 FORMAT WAJIB:\n"
        "<code>Nama Lengkap | Nomor Rekening / Wallet</code>\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚠️ Pastikan data benar sebelum kirim\n"
        "❗ Kesalahan input bukan tanggung jawab sistem\n\n"
        "💡 Contoh:\n"
        "<code>Nama | 0812345678910</code>",
        parse_mode="HTML",
        reply_markup=kb
    )

    await call.answer()
# =========================
# STEP 4 - HANDLE INPUT
# =========================

@router.message(
    F.text,
    lambda message: user_states.get(
        message.from_user.id, {}
    ).get("mode") == "wd_input"
)
async def wd_input(message: Message):

    print("=" * 50)
    print("WD_INPUT KEPANGGIL")
    print("USER:", message.from_user.id)
    print("STATE:", user_states.get(message.from_user.id))
    print("TEXT:", message.text)
    print("=" * 50)

    user_id = message.from_user.id
    state = user_states.get(user_id)

    try:
        text = message.text.strip().replace("\n", " ")
        parts = [x.strip() for x in text.split("|")]

        if len(parts) != 2:
            return await message.answer(
                "❌ Format salah\n\n"
                "Gunakan format:\n"
                "<code>Nama | Nomor</code>",
                parse_mode="HTML"
            )

        nama, nomor = parts

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users
                SET wd_method=$1,
                    wd_provider=$2,
                    wd_name=$3,
                    wd_number=$4
                WHERE user_id=$5
                """,
                state["type"],
                state["provider"],
                nama,
                nomor,
                user_id
            )

        user_states.pop(user_id, None)

        await message.answer(
            "✅ Data withdraw berhasil disimpan"
        )

    except Exception as e:
        print("WD INPUT ERROR:", repr(e))
        await message.answer(
            "❌ Gagal simpan data"
        )


# =========================
# REQUEST WITHDRAW
# =========================

@router.callback_query(F.data == "wd_request")
async def wd_request(call: CallbackQuery):

    user_id = call.from_user.id

    # 🔥 FIX: pakai wd_status yang sudah ada
    open_status, _, _ = wd_status()

    if not open_status:
        return await call.answer(
            "🔴 Withdraw sedang TUTUP",
            show_alert=True
        )

    async with db_pool.acquire() as conn:

        row = await conn.fetchrow("""
            SELECT balance, wd_method, wd_provider, wd_name, wd_number
            FROM users
            WHERE user_id=$1
        """, user_id)

    if not row:
        return await call.answer("❌ User tidak ditemukan", show_alert=True)

    # 🔥 safety fallback (biar gak None error)
    wd_method = row["wd_method"] or ""
    wd_provider = row["wd_provider"] or "-"
    wd_name = row["wd_name"] or "-"
    wd_number = row["wd_number"] or "-"

    if not wd_method:
        return await call.answer(
            "⚠️ Silakan atur rekening dulu",
            show_alert=True
        )

    if row["balance"] < MIN_WITHDRAW:
        return await call.answer(
            "❌ Saldo kurang",
            show_alert=True
        )

    await call.message.edit_text(
        "💸 <b>WITHDRAW CONFIRMATION</b>\n\n"
        f"💰 Saldo: Rp {row['balance']:,}\n"
        f"🏦 {wd_method} ({wd_provider})\n"
        f"👤 {wd_name}\n"
        f"📌 {wd_number}\n\n"
        "⚠️ Setelah lanjut, saldo akan diproses",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 PROSES WITHDRAW",
                    callback_data="wd_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 BACK",
                    callback_data="withdraw"
                )
            ]
        ])
    )
# =========================
# EXECUTE WITHDRAW
# =========================

@router.callback_query(F.data == "wd_confirm")
async def wd_confirm(call: CallbackQuery):

    user_id = call.from_user.id

    async with db_pool.acquire() as conn:

        row = await conn.fetchrow("""
            SELECT balance, wd_method, wd_provider, wd_name, wd_number
            FROM users
            WHERE user_id=$1
        """, user_id)

        if not row:
            return await call.answer("❌ User tidak ditemukan", show_alert=True)

        if row["balance"] < MIN_WITHDRAW:
            return await call.answer("❌ Saldo kurang", show_alert=True)

        if not row["wd_method"] or not row["wd_name"] or not row["wd_number"]:
            return await call.answer("❌ Data withdraw belum lengkap", show_alert=True)

        amount = row["balance"]

        await conn.execute("""
            INSERT INTO withdraws(
                user_id,
                amount,
                fee,
                net_amount,
                method,
                account_name,
                account_number,
                status
            )
            VALUES($1,$2,0,$2,$3,$4,$5,'pending')
        """,
        user_id,
        amount,
        row["wd_method"],
        row["wd_name"],
        row["wd_number"]
        )

        await conn.execute("""
            UPDATE users
            SET balance = 0,
                total_withdraw = COALESCE(total_withdraw,0) + $1
            WHERE user_id=$2
        """, amount, user_id)

    await call.message.edit_text(
        "⏳ <b>WITHDRAW PENDING</b>\n\n"
        "📌 Dana akan diproses manual oleh admin\n"
        "⏰ Estimasi 1-24 jam",
        parse_mode="HTML"
    )
        
# =========================
# KEYBOARD
# =========================

def upload_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ DONE",
                    callback_data="upload_done"
                ),
                InlineKeyboardButton(
                    text="❌ CANCEL",
                    callback_data="upload_cancel"
                )
            ]
        ]
    )

# =========================
# UP FILE CALLBACK
# =========================

@router.callback_query(F.data == "upfile")
async def up_file(call: CallbackQuery):

    user_id = call.from_user.id

    # =========================
    # ANTI SPAM
    # =========================
    if not user_limit(user_id):
        return await call.answer(
            "⏳ Jangan spam ya 😏",
            show_alert=True
        )

    # =========================
    # RESET SESSION
    # =========================
    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    # =========================
    # SET USER STATE
    # =========================
    user_states[user_id] = {
        "mode": "upload"
    }

    # =========================
    # CREATE UPLOAD SESSION
    # =========================
    upload_sessions[user_id] = {
        "video": 0,
        "photo": 0,
        "document": 0,
        "items": [],
        "msg_id": call.message.message_id,
        "price": 0,
        "share": True,
        "processing": False,
        "created_at": time.time()
    }

    # =========================
    # OPEN UPLOAD PANEL
    # =========================
    try:
        await call.message.edit_text(
            "📤 <b>UPLOAD MODE AKTIF</b>\n\n"
            "📁 Kirim media kamu sekarang.\n"
            "🖼 Foto, 🎬 Video, 📄 Dokumen didukung.\n\n"
            "✅ Tekan DONE jika sudah selesai.\n"
            "❌ Tekan CANCEL untuk membatalkan.",
            parse_mode="HTML",
            reply_markup=upload_kb()
        )

    except Exception as e:
        print(f"UPFILE ERROR: {e}")

        await call.message.answer(
            "📤 Upload mode aktif.\n"
            "Silakan kirim media kamu."
        )

    await call.answer()
# =========================
# MEDIA HANDLER (FINAL CLEAN)
# =========================

@router.message(F.photo | F.video | F.document)
async def handle_media(message: Message):

    user_id = message.from_user.id

    state = user_states.get(user_id)
    s = upload_sessions.get(user_id)

    if not state or state.get("mode") != "upload":
        return

    if not s:
        return

    # FORCE SAFE DEFAULT
    s.setdefault("items", [])
    s.setdefault("photo", 0)
    s.setdefault("video", 0)
    s.setdefault("document", 0)

    MAX_MEDIA = 100
    MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024

    file_obj = None
    file_type = None

    if message.photo:
        file_obj = message.photo[-1]
        file_type = "photo"
    elif message.video:
        file_obj = message.video
        file_type = "video"
    elif message.document:
        file_obj = message.document
        file_type = "document"

    if not file_obj:
        return

    file_id = file_obj.file_id
    file_size = getattr(file_obj, "file_size", 0) or 0

    if len(s["items"]) >= MAX_MEDIA:
        try:
            await message.delete()
        except:
            pass
        return

    current_size = sum(x.get("size", 0) for x in s["items"])

    if current_size + file_size > MAX_TOTAL_SIZE:
        try:
            await message.delete()
        except:
            pass
        return

    # COUNTER SAFE
    s[file_type] += 1

    # SAVE
    s["items"].append({
        "file_id": file_id,
        "type": file_type,
        "size": file_size
    })

    try:
        await message.delete()
    except:
        pass

    now = time.time()

    if now - last_edit_time.get(user_id, 0) < 1.5:
        return

    last_edit_time[user_id] = now

    total = len(s["items"])
    total_size = sum(x.get("size", 0) for x in s["items"])
    size_mb = round(total_size / (1024 * 1024), 2)

    progress = min(100, int((total / MAX_MEDIA) * 100))

    bar = "█" * (progress // 10) + "░" * (10 - (progress // 10))

    text = (
        "📤 <b>UPLOAD MODE</b>\n\n"
        f"📊 [{bar}] {progress}%\n\n"
        f"📁 Total File : <b>{total}</b>\n"
        f"🖼 Photo      : {s['photo']}\n"
        f"🎬 Video      : {s['video']}\n"
        f"📄 Document   : {s['document']}\n"
        f"💾 Size       : {size_mb} MB\n\n"
        "━━━━━━━━━━━━━━\n"
        "✅ Tekan DONE jika selesai"
    )

    try:
        await safe_send(
            message.bot.edit_message_text,
            chat_id=message.chat.id,
            message_id=s["msg_id"],
            text=text,
            parse_mode="HTML",
            reply_markup=upload_kb()
        )
    except Exception as e:
        print("UPLOAD PANEL ERROR:", e)
    
# =========================
# GENERATE CODE
# =========================

def generate_code(v, p, d):
    import hashlib
    import secrets

    base = f"{v}{p}{d}{secrets.token_hex(4)}"
    rand = hashlib.sha1(base.encode()).hexdigest()[:12]

    return f"bluebirdbot_{v}v_{p}p_{d}d_{rand}"


# =========================
# PRICE TYPE KB
# =========================

def price_type_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💰 Berbayar",
                    callback_data="price_paid"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆓 Gratis",
                    callback_data="price_free"
                )
            ]
        ]
    )
def media_system_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Share File",
                    callback_data="media_share"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ No Share",
                    callback_data="media_noshare"
                )
            ]
        ]
    )

# =========================
# UPLOAD DONE
# =========================

@router.callback_query(F.data == "upload_done")
async def done(call: CallbackQuery):

    user_id = call.from_user.id
    s = upload_sessions.get(user_id)

    if not s or not s.get("items"):
        return await call.answer(
            "😏 Belum ada media yang diupload",
            show_alert=True
        )

    user_states[user_id] = {
        "mode": "choose_price_type"
    }

    await call.message.edit_text(
        "💰 Pilih jenis produk:",
        reply_markup=price_type_kb()
    )

    await call.answer()


# =========================
# PRICE PAID
# =========================

@router.callback_query(F.data == "price_paid")
async def price_paid(call: CallbackQuery):

    user_id = call.from_user.id

    user_states[user_id] = {
        "mode": "set_price"
    }

    await call.message.edit_text(
        "💰 Masukkan harga media\n\n"
        "Minimal Rp1.000\n"
        "Maksimal Rp100.000\n\n"
        "Kirim angka saja."
    )

    await call.answer()


# =========================
# PRICE FREE
# =========================

@router.callback_query(F.data == "price_free")
async def price_free(call: CallbackQuery):

    user_id = call.from_user.id

    session = upload_sessions.get(user_id)

    if not session:
        return await call.answer(
            "❌ Session upload hilang",
            show_alert=True
        )

    session["price"] = 0

    user_states[user_id]["mode"] = "set_media_system"

    await call.message.edit_text(
        "🆓 Produk Gratis\n\n"
        "Pilih sistem media:",
        reply_markup=media_system_kb()
    )

    await call.answer()


# =========================
# SET PRICE
# =========================

@router.message(
    F.text,
    lambda m: user_states.get(m.from_user.id, {}).get("mode") == "set_price"
)
async def set_price(message: Message):

    user_id = message.from_user.id

    print("=" * 50)
    print("SET_PRICE KEPANGGIL")
    print("USER:", user_id)
    print("STATE:", user_states.get(user_id))
    print("TEXT:", message.text)
    print("=" * 50)

    state = user_states.get(user_id)

    if not state:
        return

    if state.get("mode") != "set_price":
        return

    session = upload_sessions.get(user_id)

    if not session:
        return await message.answer(
            "❌ Session upload hilang.\nSilakan upload ulang."
        )

    text = (
        message.text.strip()
        .replace(".", "")
        .replace(",", "")
        .replace(" ", "")
    )

    print("TEXT CLEAN =", text)

    if not text.isdigit():
        return await message.answer(
            "❌ Harga harus berupa angka.\n\n"
            "Contoh:\n"
            "2000\n"
            "2.000\n"
            "20000"
        )

    try:
        price = int(text)
    except ValueError:
        return await message.answer(
            "❌ Format harga tidak valid"
        )

    if price < 1000:
        return await message.answer(
            "❌ Minimal harga Rp1.000"
        )

    if price > 100000:
        return await message.answer(
            "❌ Maksimal harga Rp100.000"
        )

    session["price"] = price

    user_states[user_id]["mode"] = "set_media_system"

    await message.answer(
        f"💰 Harga diset Rp {price:,}".replace(",", ".") +
        "\n\nPilih sistem media:",
        reply_markup=media_system_kb()
    )
# =========================
# MEDIA SYSTEM
# =========================

@router.callback_query(
    F.data.in_(
        ["media_share", "media_noshare"]
    )
)
async def media_system(call: CallbackQuery):

    user_id = call.from_user.id

    s = upload_sessions.get(user_id)

    if not s:
        return

    s["share"] = (
        call.data == "media_share"
    )

    await save_upload(call)


# =========================
# SAVE UPLOAD
# =========================

async def save_upload(call: CallbackQuery):

    user_id = call.from_user.id
    s = upload_sessions.get(user_id)

    if not s:
        return

    if s.get("processing"):
        return await call.answer(
            "⏳ Sedang diproses..."
        )

    s["processing"] = True

    try:

        # =========================
        # GENERATE CODE
        # =========================
        code = generate_code(
            s.get("video", 0),
            s.get("photo", 0),
            s.get("document", 0)
        )

        # =========================
        # STATS
        # =========================
        total_items = len(s["items"])

        total_size = sum(
            item.get("size", 0)
            for item in s["items"]
        )

        # =========================
        # CREATOR
        # =========================
        creator = (
            f"@{call.from_user.username}"
            if call.from_user.username
            else call.from_user.full_name
        )

        # =========================
        # SETTINGS
        # =========================
        media_price = s.get("price", 0)
        share_enabled = s.get("share", True)

        price_text = (
            f"Rp {media_price:,}"
            if media_price > 0
            else "Free"
        )

        media_system_text = (
            "🔓 Share"
            if share_enabled
            else "🔒 No Share"
        )

        # =========================
        # SAVE DATABASE
        # =========================
        async with db_pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO codes(
                    code,
                    owner_id,
                    total_media,
                    total_size
                )
                VALUES($1,$2,$3,$4)
                """,
                code,
                user_id,
                total_items,
                total_size
            )

            rows = []

            for item in s["items"]:

                rows.append(
                    (
                        code,
                        item["file_id"],
                        item["type"],
                        item["size"]
                    )
                )

            if rows:

                await conn.executemany(
                    """
                    INSERT INTO medias(
                        code,
                        file_id,
                        file_type,
                        file_size
                    )
                    VALUES($1,$2,$3,$4)
                    """,
                    rows
                )

        # =========================
        # SUCCESS PANEL
        # =========================
        await call.message.edit_text(
            f"""
✅ <b>Done Complete</b>

🔑 <b>Code :</b>
<code>{code}</code>

📁 <b>Total Media :</b> {total_items}
💾 <b>Total Size :</b> {round(total_size / (1024 * 1024), 2)} MB

💰 <b>Price Media :</b> {price_text}
📡 <b>Sistem Media :</b> {media_system_text}
👤 <b>Create By :</b> {creator}

🚀 <b>Media berhasil disimpan</b>
            """,
            parse_mode="HTML"
        )

    except Exception as e:

        print("SAVE ERROR:", e)

        try:
            await call.message.edit_text(
                "❌ Gagal proses upload"
            )
        except Exception:
            pass

    finally:

        # =========================
        # CLEAN SESSION
        # =========================
        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        last_edit_time.pop(user_id, None)
        
# =========================
# CANCEL HANDLER
# =========================

@router.callback_query(F.data == "upload_cancel")
async def cancel(call: CallbackQuery):

    user_id = call.from_user.id
    username = call.from_user.username or "No Username"

    # =========================
    # CLEAN SESSION
    # =========================
    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    try:

        # =========================
        # BUILD DASHBOARD
        # =========================
        text, keyboard = await build_dashboard(
            user_id,
            username
        )

        # =========================
        # RETURN TO HOME
        # =========================
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:

        print("CANCEL ERROR:", e)

        try:
            await call.message.answer(
                "🏠 Upload dibatalkan."
            )
        except Exception:
            pass

    await call.answer(
        "❌ Upload dibatalkan"
    )
# =========================
# GLOBAL
# =========================

COOLDOWN_TIME = 5

# =========================
# NORMALIZER
# =========================
def normalize_type(t):
    t = (t or "").lower().strip()
    if t in ["photo", "image", "img"]:
        return "photo"
    if t in ["video", "vid"]:
        return "video"
    return "document"


# =========================
# COOLDOWN
# =========================
def is_cooldown(user_id):
    now = time.time()
    last = cooldown["global"].get(user_id, 0)

    if now - last < COOLDOWN_TIME:
        return True

    cooldown["global"][user_id] = now
    return False


# =========================
# LOAD MEDIA
# =========================
async def load_media(code: str):
    if not code:
        return []

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT file_id, file_type, COALESCE(file_size,0) AS file_size
                FROM medias
                WHERE code=$1
                ORDER BY id ASC
            """, code)
    except Exception as e:
        print("DB ERROR:", e)
        return []

    return [
        {
            "file_id": r["file_id"],
            "file_type": normalize_type(r["file_type"]),
            "file_size": r["file_size"]
        }
        for r in rows
    ]


# =========================
# SEND MEDIA (ANTI BAN SAFE)
# =========================
async def send_media(bot, chat_id: int, chunk: list):

    if not chunk:
        return False

    media = []

    for m in chunk[:5]:

        fid = m.get("file_id")
        ftype = (m.get("file_type") or "").lower()

        if not fid:
            continue

        try:

            if ftype == "photo":
                media.append(
                    InputMediaPhoto(media=fid)
                )

            elif ftype == "video":
                media.append(
                    InputMediaVideo(media=fid)
                )

            else:
                media.append(
                    InputMediaDocument(media=fid)
                )

        except Exception as e:
            print("MEDIA BUILD ERROR:", e)

    if not media:
        return False

    for attempt in range(5):

        try:

            await global_throttle()

            await bot.send_media_group(
                chat_id=chat_id,
                media=media
            )

            return True

        except TelegramRetryAfter as e:

            print(
                f"FLOODWAIT {e.retry_after}s"
            )

            await asyncio.sleep(
                e.retry_after + 1
            )

        except TelegramBadRequest as e:

            print(
                "BAD REQUEST:",
                e
            )

            return False

        except Exception as e:

            print(
                f"SEND MEDIA ERROR {attempt+1}:",
                e
            )

            await asyncio.sleep(
                1 + attempt
            )

    print(
        "❌ GAGAL KIRIM MEDIA"
    )

    return False
    
# =========================
# KEYBOARD
# =========================
def build_kb(user_id, page, total_pages):

    history = page_history.get(user_id, set())
    rows = []

    prev_btn = InlineKeyboardButton(
        text="⬅ Prev" if page > 0 else "⛔ Prev",
        callback_data="prev" if page > 0 else "noop"
    )

    next_btn = InlineKeyboardButton(
        text="➡ Next" if page < total_pages - 1 else "⛔ Next",
        callback_data="next" if page < total_pages - 1 else "noop"
    )

    rows.append([prev_btn, next_btn])

    # page indicator
    window = 5
    start = max(0, page - 2)
    end = min(total_pages, start + window)

    page_row = []
    for i in range(start, end):

        if i == page:
            mark = "🟢"
        elif i in history:
            mark = "🟡"
        else:
            mark = "⚪"

        page_row.append(
            InlineKeyboardButton(
                text=f"{i+1}{mark}",
                callback_data=f"page:{i}"
            )
        )

    if page_row:
        rows.append(page_row)

    # =========================
    # LINK BUTTONS (FIXED)
    # =========================
    rows.append([
        InlineKeyboardButton(
            text="📢 CHANNEL UPDATE",
            url="https://t.me/+3g_yhHwxCrc5ZTg9"
        ),
        InlineKeyboardButton(
            text="💬 GROUP CHAT",
            url="https://t.me/+1tipdp-NTywzODhl"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
# =========================
# RENDER PAGE (FIX PANEL BAWAH)
# =========================

async def render_page(user_id: int, bot, chat_id: int):

    state = user_states.get(user_id)

    if not state:
        return

    data = state.get("data") or []

    if not data:
        return

    page = state.get("page", 0)
    size = state.get("page_size", 5)

    total_pages = max(
        1,
        (len(data) + size - 1) // size
    )

    page = max(
        0,
        min(page, total_pages - 1)
    )

    state["page"] = page

    start = page * size
    end = start + size

    chunk = data[start:end]

    # =========================
    # HISTORY
    # =========================

    page_history.setdefault(
        user_id,
        set()
    ).add(page)

    # =========================
    # SEND MEDIA
    # =========================

    try:

        await send_media(
            bot,
            chat_id,
            chunk
        )

    except Exception as e:

        print(
            "SEND MEDIA ERROR:",
            e
        )

    # =========================
    # PANEL TEXT
    # =========================

    text = (
        f"📦 CODE: <code>{state.get('code','-')}</code>\n"
        f"📄 Page: {page + 1}/{total_pages}\n"
        f"📁 Media: {start + 1}-{start + len(chunk)} / {len(data)}\n\n"
        "👇 CONTROL PANEL DI BAWAH"
    )

    kb = build_kb(
        user_id,
        page,
        total_pages
    )

    # =========================
    # DELETE PANEL LAMA
    # =========================

    panel_id = state.get("last_panel_msg")

    if panel_id:

        try:

            await safe_send(
                bot.delete_message,
                chat_id=chat_id,
                message_id=panel_id
            )

        except Exception as e:

            print(
                "DELETE PANEL ERROR:",
                e
            )

    # =========================
    # CREATE PANEL BARU
    # =========================

    try:

        msg = await safe_send(
            bot.send_message,
            chat_id=chat_id,
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )

        if msg:
            state["last_panel_msg"] = msg.message_id

    except Exception as e:

        print(
            "SEND PANEL ERROR:",
            e
        )

# =========================
# PAGINATION LOCK
# =========================
pagination_lock = defaultdict(asyncio.Lock)

# =========================
# SINGLE PAGINATION HANDLER
# =========================
@router.callback_query(
    F.data.in_(["next", "prev"]) |
    F.data.startswith("page:")
)
async def pagination(call: CallbackQuery):

    user_id = call.from_user.id

    # =========================
    # LOCK USER (ANTI SPAM CLICK)
    # =========================
    async with pagination_lock[user_id]:

        state = user_states.get(user_id)

        if not state:
            return await call.answer(
                "Session expired",
                show_alert=True
            )

        data = state.get("data") or []

        if not data:
            return await call.answer(
                "No data",
                show_alert=True
            )

        old_page = state.get(
            "page",
            0
        )

        size = state.get(
            "page_size",
            5
        )

        max_page = (
            len(data) - 1
        ) // size

        page = old_page

        # =========================
        # PAGE CONTROL
        # =========================
        if call.data == "next":

            page += 1

        elif call.data == "prev":

            page -= 1

        else:

            try:

                page = int(
                    call.data.split(":")[1]
                )

            except Exception:

                return await call.answer(
                    "Error"
                )

        page = max(
            0,
            min(page, max_page)
        )

        # =========================
        # NO CHANGE
        # =========================
        if page == old_page:
            return await call.answer()

        state["page"] = page

        # =========================
        # RENDER PAGE
        # =========================
        await render_page(
            user_id,
            call.bot,
            call.message.chat.id
        )

        await call.answer()

# =========================
# NOOP
# =========================
@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):

    await call.answer(
        "😏 FULL JANCOK"
    )
# =========================
# START GET FILE
# =========================
@router.callback_query(F.data == "getfile")
async def start_get(call: CallbackQuery):

    user_id = call.from_user.id
    state = user_states.get(user_id, {})

    # kalau sedang upload → jangan ganggu
    if state.get("mode") == "upload":
        return await call.answer(
            "❌ Selesaikan upload dulu",
            show_alert=True
        )

    # reset semua state yang konflik
    user_states[user_id] = {
        "mode": "getfile",
        "step": "input_code"
    }

    upload_sessions.pop(user_id, None)

    await call.message.edit_text(
        "📥 Kirim CODE 😏"
    )

    await call.answer()
# =========================
# RECEIVE CODE
# =========================
@router.message(F.text.regexp(r"^bluebirdbot_"))
async def receive_code(message: Message):

    user_id = message.from_user.id
    state = user_states.get(user_id)

    if not state or state.get("mode") != "getfile":
        return

    if is_cooldown(user_id):
        return await message.answer("⏳ Jangan spam")

    codes = re.findall(
        r"bluebirdbot_\d+v_\d+p_\d+d_[a-f0-9]{12}",
        message.text or ""
    )

    if not codes:
        return await message.answer("❌ CODE salah")

    codes = list(dict.fromkeys(codes))[:3]

    all_data = []

    for code in codes:

        data = await load_media(code)

        if data:
            all_data.extend(data)

        await asyncio.sleep(0.1)

    if not all_data:
        return await message.answer("❌ Tidak ditemukan")

    all_data = all_data[:50]

    # =========================
    # HAPUS PANEL LAMA
    # =========================

    old_state = user_states.get(user_id)

    if old_state:

        old_panel = old_state.get(
            "last_panel_msg"
        )

        if old_panel:

            try:

                await message.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=old_panel
                )

            except Exception:
                pass

    # =========================
    # BUAT SESSION BARU
    # =========================

    user_states[user_id] = {
        "mode": "view",
        "code": codes[0],
        "page": 0,
        "page_size": 5,
        "data": all_data,
        "last_panel_msg": None
    }

    page_history[user_id] = set()

    await message.answer(
        f"📦 Ditemukan {len(all_data)} file"
    )

    # =========================
    # RENDER PAGE PERTAMA
    # =========================

    await render_page(
        user_id,
        message.bot,
        message.chat.id
    )
# ======================
# ADD USER FUNCTION
# =========================

async def add_user(
    user_id,
    username,
    fullname
):

    async with db_pool.acquire() as conn:

        await conn.execute(
            """
            INSERT INTO users
            (user_id,username,fullname)

            VALUES($1,$2,$3)

            ON CONFLICT(user_id)

            DO UPDATE SET

            username=$2,
            fullname=$3
            """,

            user_id,
            username,
            fullname
        )

# =========================
# ACCOUNT
# =========================

@router.message(F.text == "/account")
async def account_cmd(message: Message):

    user = message.from_user

    # =========================
    # SAVE USER
    # =========================
    await add_user(
        user.id,
        user.username or "",
        user.full_name or "No Name"
    )

    async with db_pool.acquire() as conn:

        codes = await conn.fetch(
            """
            SELECT code, total_media, total_size
            FROM codes
            WHERE owner_id = $1
            ORDER BY id DESC
            LIMIT 10
            """,
            user.id
        )

        total_codes = await conn.fetchval(
            "SELECT COUNT(*) FROM codes WHERE owner_id = $1",
            user.id
        )

    # =========================
    # FORMAT CODE LIST
    # =========================
    if codes:
        code_lines = []
        for c in codes:
            code_lines.append(
                f"📦 <code>{c['code']}</code>\n"
                f"   └ {c['total_media']} file"
            )

        code_text = "\n".join(code_lines)

    else:
        code_text = "❌ Belum ada code"

    # =========================
    # FORMAT USER
    # =========================
    username = f"@{user.username}" if user.username else "Tidak ada"

    text = (
        "👤 <b>ACCOUNT INFO</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"👤 <b>Name:</b> {user.full_name}\n"
        f"🔗 <b>Username:</b> {username}\n\n"
        f"📊 <b>Total Code:</b> {total_codes}\n\n"
        f"📁 <b>Last Code:</b>\n{code_text}"
    )

    await message.answer(text, parse_mode="HTML")
# =========================
# VIP KEYBOARD
# =========================
def vip_kb():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 CHAT ADMIN VIP",
                    url="https://t.me/penngewe"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="vip_cancel"
                )
            ]
        ]
    )
# =========================
# VIP COMMAND
# =========================
@router.message(F.text == "/vip")
async def vip_cmd(message: Message):

    text = (
        "💎 <b>VIP ACCESS</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔥 <b>BENEFIT VIP</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "⚡ Unlimited Upload File\n"
        "⚡ Priority Processing (No Queue)\n"
        "⚡ Fast Get File Access\n"
        "⚡ Anti Limit System\n"
        "⚡ Full Media Support\n\n"
        "━━━━━━━━━━━━━━\n"
        "📦 <b>STORAGE INFO</b>\n"
        "━━━━━━━━━━━━━━\n"
        "📁 Media disimpan di channel database\n"
        "🔒 Aman via CODE system\n\n"
        "━━━━━━━━━━━━━━\n"
        "💀 <b>NOTICE</b>\n"
        "━━━━━━━━━━━━━━\n"
        "• VIP = akses, bukan privilege manja\n"
        "• Semua tetap pakai sistem\n"
        "• Salah pakai = tanggung sendiri 😏"
    )

    await message.answer(
        text,
        reply_markup=vip_kb(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# =========================
# VIP CANCEL
# =========================
@router.callback_query(F.data == "vip_cancel")
async def vip_cancel(call: CallbackQuery):

    try:
        await call.message.edit_text(
            "❌ <b>VIP CLOSED</b>\n\n"
            "😏 Balik ke mode gratisan.\n"
            "Kalau serius, jangan cuma klik.",
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer()
# =========================
# ADMIN CHECK
# =========================
def is_admin(user_id: int):
    return user_id in ADMINS


# =========================
# ADD ADMIN
# =========================
@router.message(F.text.startswith("/addadmin"))
async def add_admin(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer(
            "🚫 ACCESS DENIED\n\nLu siapa 😏"
        )

    parts = message.text.split()

    if len(parts) != 2:
        return await message.answer(
            "❌ Format:\n/addadmin <user_id>"
        )

    # =========================
    # VALIDATE
    # =========================
    try:
        uid = int(parts[1])
    except:
        return await message.answer("❌ ID harus angka")

    # =========================
    # PREVENT DUPLICATE
    # =========================
    if uid in ADMINS:
        return await message.answer(
            "⚠️ Sudah admin 😏"
        )

    # =========================
    # ADD
    # =========================
    ADMINS.add(uid)

    print(f"[ADMIN] Added: {uid} by {message.from_user.id}")

    await message.answer(
        f"💀 ADMIN ADDED\n\nID: {uid}"
    )


# =========================
# REMOVE ADMIN (WAJIB ADA)
# =========================
@router.message(F.text.startswith("/deladmin"))
async def del_admin(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 No access")

    parts = message.text.split()

    if len(parts) != 2:
        return await message.answer(
            "❌ Format:\n/deladmin <user_id>"
        )

    try:
        uid = int(parts[1])
    except:
        return await message.answer("❌ ID invalid")

    # =========================
    # PROTECT
    # =========================
    if uid == message.from_user.id:
        return await message.answer(
            "⚠️ Gak bisa hapus diri sendiri 😏"
        )

    if uid not in ADMINS:
        return await message.answer(
            "❌ Bukan admin"
        )

    ADMINS.remove(uid)

    print(f"[ADMIN] Removed: {uid} by {message.from_user.id}")

    await message.answer(
        f"💀 ADMIN REMOVED\n\nID: {uid}"
    )

# =========================
# STATISTIC (UPGRADE)
# =========================
@router.message(F.text == "/stat")
async def stat_cmd(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 ACCESS DENIED")

    try:
        async with db_pool.acquire() as conn:

            users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            codes = await conn.fetchval("SELECT COUNT(*) FROM codes") or 0
            media = await conn.fetchval("SELECT COUNT(*) FROM medias") or 0

            total_size = await conn.fetchval(
                "SELECT COALESCE(SUM(total_size),0) FROM codes"
            ) or 0

    except Exception as e:
        print("STAT ERROR:", e)
        return await message.answer("⚠️ DATABASE ERROR")

    mb = total_size / (1024 * 1024)

    await message.answer(
        "📊 <b>SYSTEM STATISTICS</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 Users   : {users}\n"
        f"🔑 Codes   : {codes}\n"
        f"📦 Media   : {media}\n"
        f"💾 Storage : {mb:.2f} MB\n"
        "━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )


# =========================
# BROADCAST (DEWA VERSION - FIXED)
# =========================
@router.message(F.text.startswith("/broadcast"))
async def broadcast_cmd(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 ACCESS DENIED")

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        return await message.answer("❌ Format:\n/broadcast pesan")

    # =========================
    # LOAD USERS
    # =========================
    try:
        async with db_pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id FROM users")
    except Exception as e:
        print("BC ERROR:", e)
        return await message.answer("⚠️ DATABASE ERROR")

    total = len(users)
    sent = 0
    failed = 0

    start_time = time.time()

    status = await message.answer(
        f"📡 <b>BROADCAST STARTED</b>\n\n"
        f"👥 Total user: {total}\n"
        f"⏳ Progress: 0%\n\n"
        "💀 System running...",
        parse_mode="HTML"
    )

    # =========================
    # LOOP
    # =========================
    for i, user in enumerate(users, start=1):

        try:
            await message.bot.send_message(
                chat_id=user["user_id"],
                text=text
            )
            sent += 1

        except Exception as e:
            failed += 1
            print(f"[BROADCAST ERROR] user {user['user_id']}:", repr(e))

        # =========================
        # SMART DELAY (ANTI FLOOD STABLE)
        # =========================
        if i % 25 == 0:
            await asyncio.sleep(1.5)   # heavy cooldown tiap batch
        else:
            await asyncio.sleep(0.08)  # safe normal delay

        # =========================
        # UPDATE PROGRESS
        # =========================
        if i % 25 == 0:
            percent = (i / total) * 100

            try:
                await status.edit_text(
                    f"📡 <b>BROADCAST RUNNING</b>\n\n"
                    f"👥 Total   : {total}\n"
                    f"📤 Sent    : {sent}\n"
                    f"❌ Failed  : {failed}\n"
                    f"⏳ Progress: {percent:.1f}%\n\n"
                    "⚡ Please wait...",
                    parse_mode="HTML"
                )
            except Exception as e:
                print("EDIT STATUS ERROR:", repr(e))

    # =========================
    # DONE
    # =========================
    duration = time.time() - start_time

    await status.edit_text(
        "📡 <b>BROADCAST FINISHED</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        f"👥 Total   : {total}\n"
        f"📤 Sent    : {sent}\n"
        f"❌ Failed  : {failed}\n"
        f"⏱ Time    : {duration:.1f}s\n"
        "━━━━━━━━━━━━━━\n\n"
        "💀 Mission complete 😏",
        parse_mode="HTML"
    )

# =========================
# HELP MENU SYSTEM
# =========================

from datetime import datetime

HELP_TEXT = (
    "🔥 <b>DECODEFILE BOT</b>\n\n"
    "Selamat datang di pusat bantuan.\n\n"
    "Pilih menu yang ingin kamu lihat di bawah."
)

# =========================
# KEYBOARD
# =========================

def help_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💸 Withdraw",
                    callback_data="help_withdraw"
                ),
                InlineKeyboardButton(
                    text="🏦 Set Bank",
                    callback_data="help_bank"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Status WD",
                    callback_data="help_status"
                ),
                InlineKeyboardButton(
                    text="🔒 Privasi",
                    callback_data="help_privacy"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤖 Status Bot",
                    callback_data="help_bot"
                ),
                InlineKeyboardButton(
                    text="ℹ️ Tentang",
                    callback_data="help_about"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Home",
                    callback_data="home"
                )
            ]
        ]
    )


def back_help_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏠 Home",
                    callback_data="home"
                ),
                InlineKeyboardButton(
                    text="🔙 Kembali",
                    callback_data="back_help"
                )
            ]
        ]
    )

# =========================
# HELP COMMAND
# =========================

@router.message(F.text == "/help")
async def help_cmd(message: Message):

    await message.answer(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_kb()
    )


@router.message(F.text == "❓ Help")
async def help_button(message: Message):

    await message.answer(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_kb()
    )
@router.callback_query(F.data == "help")
async def help_callback(call: CallbackQuery):

    await call.message.edit_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_kb()
    )

    await call.answer()

# =========================
# WITHDRAW
# =========================

@router.callback_query(F.data == "help_withdraw")
async def help_withdraw(call: CallbackQuery):

    await call.message.edit_text(
        "💸 <b>WITHDRAW SYSTEM</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 INFORMASI\n"
        "━━━━━━━━━━━━━━\n"
        "• Withdraw dilakukan melalui sistem.\n"
        "• Request akan masuk ke admin.\n"
        "• Status: Pending → Process → Success.\n"
        "• Pastikan data rekening benar.\n\n"
        "━━━━━━━━━━━━━━\n"
        "⚠️ PENTING\n"
        "━━━━━━━━━━━━━━\n"
        "Kesalahan nama rekening,\n"
        "nomor rekening atau e-wallet\n"
        "menjadi tanggung jawab pengguna.",
        parse_mode="HTML",
        reply_markup=back_help_kb()
    )

    await call.answer()

# =========================
# BANK
# =========================

@router.callback_query(F.data == "help_bank")
async def help_bank(call: CallbackQuery):

    await call.message.edit_text(
        "🏦 <b>SET BANK / EWALLET</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 DATA YANG DISIMPAN\n"
        "━━━━━━━━━━━━━━\n"
        "• Nama Pemilik\n"
        "• Nama Bank / Ewallet\n"
        "• Nomor Rekening\n\n"
        "━━━━━━━━━━━━━━\n"
        "⚠️ PERINGATAN\n"
        "━━━━━━━━━━━━━━\n"
        "Periksa kembali data sebelum menyimpan.\n"
        "Kesalahan transfer akibat data salah\n"
        "bukan tanggung jawab admin.",
        parse_mode="HTML",
        reply_markup=back_help_kb()
    )

    await call.answer()

# =========================
# STATUS WD
# =========================

@router.callback_query(F.data == "help_status")
async def help_status(call: CallbackQuery):

    await call.message.edit_text(
        "📊 <b>STATUS WITHDRAW</b>\n\n"
        "🟡 Pending\n"
        "Menunggu pengecekan admin.\n\n"
        "🔵 Process\n"
        "Sedang diproses.\n\n"
        "🟢 Success\n"
        "Dana berhasil dikirim.\n\n"
        "🔴 Rejected\n"
        "Request ditolak.\n\n"
        "Status dapat berubah sewaktu-waktu "
        "sesuai proses admin.",
        parse_mode="HTML",
        reply_markup=back_help_kb()
    )

    await call.answer()

# =========================
# PRIVACY
# =========================

@router.callback_query(F.data == "help_privacy")
async def help_privacy(call: CallbackQuery):

    await call.message.edit_text(
        "🔒 <b>PRIVASI & KEAMANAN</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 DATA USER\n"
        "━━━━━━━━━━━━━━\n"
        "• User ID\n"
        "• Username\n"
        "• Nama pengguna\n"
        "• Data rekening yang disimpan user\n\n"
        "━━━━━━━━━━━━━━\n"
        "🛡 KEAMANAN\n"
        "━━━━━━━━━━━━━━\n"
        "• File hanya dapat diakses menggunakan CODE.\n"
        "• Data tidak dibagikan ke pihak ketiga.\n"
        "• Pengguna wajib menjaga CODE miliknya.\n"
        "• Jangan bagikan data pribadi kepada orang lain.",
        parse_mode="HTML",
        reply_markup=back_help_kb()
    )

    await call.answer()

# =========================
# BOT STATUS
# =========================

@router.callback_query(F.data == "help_bot")
async def help_bot(call: CallbackQuery):

    year = datetime.now().year

    await call.message.edit_text(
        "🤖 <b>BOT STATUS</b>\n\n"
        "🟢 Status : Online\n"
        "⚡ Sistem : Aktif\n"
        "🔖 Version : v2.0\n"
        "📦 Storage : Online\n"
        "🔒 Security : Active\n\n"
        f"© {year} DecodeFile Bot",
        parse_mode="HTML",
        reply_markup=back_help_kb()
    )

    await call.answer()

# =========================
# ABOUT
# =========================

@router.callback_query(F.data == "help_about")
async def help_about(call: CallbackQuery):

    await call.message.edit_text(
        "ℹ️ <b>TENTANG BOT</b>\n\n"
        "DecodeFile Bot adalah sistem penyimpanan "
        "dan pengambilan file berbasis CODE.\n\n"
        "━━━━━━━━━━━━━━\n"
        "FITUR\n"
        "━━━━━━━━━━━━━━\n"
        "📤 Upload File\n"
        "📥 Get File\n"
        "🏦 Set Bank / Ewallet\n"
        "💸 Withdraw System\n"
        "📊 Status Withdraw\n"
        "🔒 Privacy & Security\n\n"
        "Bot dirancang untuk memudahkan "
        "pengelolaan file dan transaksi pengguna.",
        parse_mode="HTML",
        reply_markup=back_help_kb()
    )

    await call.answer()

# =========================
# BACK
# =========================

@router.callback_query(F.data == "back_help")
async def back_help(call: CallbackQuery):

    await call.message.edit_text(
        HELP_TEXT,
        parse_mode="HTML",
        reply_markup=help_kb()
    )

    await call.answer()

# =========================
# CLEANUP MEMORY
# =========================

async def cleanup_task():

    while True:

        await asyncio.sleep(600)

        now = time.time()

        for uid in list(user_last_action):

            # 6 JAM TIDAK AKTIF
            if now - user_last_action[uid] > 21600:

                user_last_action.pop(uid, None)

                page_history.pop(uid, None)

                user_states.pop(uid, None)

                upload_sessions.pop(uid, None)

                last_edit_time.pop(uid, None)

# =========================
# STARTUP (FIXED FINAL)
# =========================

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    # =========================
    # INIT DATABASE
    # =========================
    try:
        await init_db()
        print("✅ DB INIT OK")
    except Exception as e:
        print("❌ DB INIT FAILED:", repr(e))
        return

    # =========================
    # BACKGROUND TASK
    # =========================
    asyncio.create_task(cleanup_task())

    print("🔥 BOT STARTED")

    try:
        await dp.start_polling(bot)

    except Exception as e:
        print("❌ BOT ERROR:", repr(e))

    finally:
        print("💀 SHUTDOWN...")

        global db_pool
        if db_pool:
            try:
                await db_pool.close()
            except Exception as e:
                print("❌ DB CLOSE ERROR:", repr(e))
            db_pool = None

        try:
            await bot.session.close()
        except Exception as e:
            print("❌ BOT SESSION CLOSE ERROR:", repr(e))


# =========================
# RUNNER (CLEAN FIX)
# =========================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 STOPPED")
    except Exception as e:
        print("❌ FATAL:", repr(e))
