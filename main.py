# =========================
# IMPORTS (STANDARD)
# =========================
import os
import asyncio
import time
import random
import secrets
import string
import hashlib
import hmac
import aiogram
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# =========================
# THIRD PARTY
# =========================
import asyncpg
import httpx
import uvicorn
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
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

print("AIROGRAM VERSION:", aiogram.__version__)
# =========================
# ROUTER
# =========================
router = Router()


# =========================
# LOAD ENV
# =========================
load_dotenv()


# =========================
# CORE CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

ADMINS = {
    int(x)
    for x in os.getenv("ADMINS", "").split(",")
    if x.strip().isdigit()
}

FORCE_CHANNEL = int(os.getenv("FORCE_CHANNEL", "-1003712587847"))
FORCE_CHANNEL_LINK = os.getenv(
    "FORCE_CHANNEL_LINK",
    "https://t.me/+3g_yhHwxCrc5ZTg9"
)

UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL")
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL", "0") or 0)

VIP_LINK = os.getenv("VIP_LINK")


# =========================
# PAYMENT CONFIG (BAYARGG)
# =========================
BAYARGG_API_URL = "https://www.bayar.gg/api/create-payment.php"
BAYARGG_API_KEY = os.getenv("BAYARGG_API_KEY")


# =========================
# APP + DB POOL
# =========================
app = FastAPI()
db_pool = None


async def init_db():
    global db_pool

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
        -- USERS (NO DEPOSIT SYSTEM)
        -- =========================
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            fullname TEXT,
            balance BIGINT DEFAULT 0,
            total_earn BIGINT DEFAULT 0,
            total_withdraw BIGINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- =========================
        -- MARKETPLACE CODES
        -- =========================
        CREATE TABLE IF NOT EXISTS codes(
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            owner_id BIGINT,
            price BIGINT DEFAULT 0,
            is_free BOOLEAN DEFAULT FALSE,
            allow_share BOOLEAN DEFAULT TRUE,
            total_media INT,
            total_size BIGINT,
            sales_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_codes_owner ON codes(owner_id);

        -- =========================
        -- MEDIA STORAGE
        -- =========================
        CREATE TABLE IF NOT EXISTS medias(
            id SERIAL PRIMARY KEY,
            code TEXT,
            file_id TEXT,
            file_type TEXT,
            file_size BIGINT
        );

        CREATE INDEX IF NOT EXISTS idx_medias_code ON medias(code);

        -- =========================
        -- PURCHASES (BUY SYSTEM)
        -- =========================
        CREATE TABLE IF NOT EXISTS purchases(
            id SERIAL PRIMARY KEY,
            invoice_id TEXT UNIQUE,
            buyer_id BIGINT,
            code TEXT,
            price BIGINT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- =========================
        -- WITHDRAW SYSTEM
        -- =========================
        CREATE TABLE IF NOT EXISTS withdraws(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount BIGINT,
            fee BIGINT DEFAULT 0,
            net_amount BIGINT,
            method TEXT,
            account_name TEXT,
            account_number TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW(),
            processed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_withdraw_user ON withdraws(user_id);

        -- =========================
        -- PAYMENT METHODS
        -- =========================
        CREATE TABLE IF NOT EXISTS user_payment_methods(
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            method TEXT,
            account_name TEXT,
            account_number TEXT,
            is_default BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_payment_user ON user_payment_methods(user_id);
        """)
# =========================
# FASTAPI APP
# =========================
app = FastAPI()


# =========================
# CACHE / MEMORY
# =========================
cooldown = {"global": {}, "page": {}}

page_history = {}
page_cooldown = {}
user_click_lock = {}
upload_sessions = {}
user_states = {}
last_edit_time = {}
force_cache = {}

COOLDOWN_TIME = 5

# lock untuk pagination (anti race UI)
pagination_lock = defaultdict(asyncio.Lock)


# =========================
# RATE LIMIT / ANTI SPAM
# =========================
GLOBAL_DELAY = 0.08
USER_DELAY = 1.5

last_global_send = 0
user_last_action = {}

global_lock = asyncio.Lock()


def user_limit(user_id: int) -> bool:
    """
    Limit spam per user (simple cooldown)
    """
    now = time.time()
    last = user_last_action.get(user_id)

    if last and now - last < USER_DELAY:
        return False

    user_last_action[user_id] = now
    return True


async def global_throttle():
    """
    Global Telegram API throttle (anti flood)
    """
    global last_global_send

    async with global_lock:
        now = time.time()
        diff = now - last_global_send

        if diff < GLOBAL_DELAY:
            await asyncio.sleep(GLOBAL_DELAY - diff)

        last_global_send = time.time()


async def safe_send(func, *args, **kwargs):
    """
    Safe Telegram API wrapper:
    - throttle global
    - retry
    - timeout protection
    """
    for attempt in range(5):
        try:
            await global_throttle()

            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=20
            )

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

        except TelegramBadRequest as e:
            print("BAD REQUEST:", e)
            return None

        except asyncio.TimeoutError:
            await asyncio.sleep(1 + attempt)

        except Exception as e:
            print("ERROR:", repr(e))
            await asyncio.sleep(1 + attempt)

    return None


# =========================
# ACCESS CONTROL (MARKETPLACE)
# =========================
paid_users = defaultdict(set)


def has_access(user_id: int, code: str, free_codes: set | None = None) -> bool:
    """
    Check apakah user punya akses ke code
    """
    if free_codes and code in free_codes:
        return True

    return user_id in paid_users.get(code, set())


# =========================
# DATABASE HELPER
# =========================
async def get_balance(user_id: int) -> int:
    """
    Ambil saldo user
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT balance FROM users WHERE user_id=$1",
            user_id
        )
        return row["balance"] if row else 0


# =========================
# BAYAR.GG CONFIG
# =========================
BAYARGG_SECRET = os.getenv("BAYARGG_SECRET", "SECRET_KAMU")

processed_invoices = set()
processed_lock = asyncio.Lock()


# =========================
# SIGNATURE VERIFY
# =========================
def verify_signature(data: dict, signature: str) -> bool:
    required_fields = ["invoice_id", "amount", "status", "timestamp"]

    if not all(k in data for k in required_fields):
        return False

    raw = (
        f"{data['invoice_id']}:"
        f"{data['amount']}:"
        f"{data['status'].upper()}:"
        f"{data['timestamp']}:"
        f"{BAYARGG_SECRET}"
    )

    expected = hashlib.sha256(raw.encode()).hexdigest()
    return hmac.compare_digest(expected, signature or "")


# =========================
# WEBHOOK BAYARGG
# =========================
@app.post("/bayargg/webhook")
async def bayargg_webhook(req: Request):
    data = await req.json()

    invoice_id = data.get("invoice_id")
    status = data.get("status")
    signature = data.get("signature")
    timestamp = data.get("timestamp")

    # -------------------------
    # BASIC VALIDATION
    # -------------------------
    if not all([invoice_id, status, signature, timestamp]):
        raise HTTPException(status_code=400, detail="Missing fields")

    try:
        ts = int(timestamp)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid timestamp")

    # anti replay (5 menit)
    if abs(int(time.time()) - ts) > 300:
        raise HTTPException(status_code=403, detail="Request expired")

    # signature check
    if not verify_signature(data, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # only paid
    if status.upper() != "PAID":
        return {"ok": False, "msg": "ignored status"}

    # -------------------------
    # IDEMPOTENCY (ANTI DOUBLE PAYMENT)
    # -------------------------
    async with processed_lock:
        if invoice_id in processed_invoices:
            return {"ok": True, "msg": "already processed"}
        processed_invoices.add(invoice_id)

    # -------------------------
    # MARKETPLACE LOGIC
    # -------------------------
    async with db_pool.acquire() as conn:
        async with conn.transaction():

            # ambil transaksi pembelian
            purchase = await conn.fetchrow(
                """
                SELECT code, buyer_id, price, status
                FROM purchases
                WHERE invoice_id=$1
                FOR UPDATE
                """,
                invoice_id
            )

            if not purchase:
                return {"ok": False, "msg": "purchase not found"}

            if purchase["status"] == "paid":
                return {"ok": True, "msg": "already processed (db)"}

            code = purchase["code"]
            buyer_id = purchase["buyer_id"]
            price = purchase["price"]

            # ambil owner code
            market = await conn.fetchrow(
                "SELECT owner_id FROM codes WHERE code=$1",
                code
            )

            if not market:
                return {"ok": False, "msg": "code not found"}

            owner_id = market["owner_id"]

            # -------------------------
            # MARK PURCHASE PAID
            # -------------------------
            await conn.execute(
                """
                UPDATE purchases
                SET status='paid'
                WHERE invoice_id=$1
                """,
                invoice_id
            )

            # -------------------------
            # ADD BALANCE TO CREATOR (INI INTI SYSTEM)
            # -------------------------
            await conn.execute(
                """
                UPDATE users
                SET balance = balance + $1,
                    total_earn = COALESCE(total_earn, 0) + $1
                WHERE user_id = $2
                """,
                price, owner_id
            )

            # -------------------------
            # SALES COUNT
            # -------------------------
            await conn.execute(
                """
                UPDATE codes
                SET sales_count = COALESCE(sales_count, 0) + 1
                WHERE code = $1
                """,
                code
            )

    return {"ok": True, "msg": "marketplace payment processed"}


# =========================
# USD RATE CACHE
# =========================
USD_RATE_CACHE = {
    "rate": 0.0000625,
    "last_update": 0
}

USD_CACHE_TTL = 600


# =========================
# GET USD RATE (CACHED)
# =========================
async def get_usd_rate():
    now = time.time()

    if now - USD_RATE_CACHE["last_update"] < USD_CACHE_TTL:
        return USD_RATE_CACHE["rate"]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.exchangerate.host/latest?base=IDR&symbols=USD"
            )

            data = r.json()

            rate = data.get("rates", {}).get("USD")
            if not rate:
                return USD_RATE_CACHE["rate"]

            USD_RATE_CACHE["rate"] = rate
            USD_RATE_CACHE["last_update"] = now

            return rate

    except Exception as e:
        print("USD RATE ERROR:", repr(e))
        return USD_RATE_CACHE["rate"]


# =========================
# DASHBOARD BUILDER
# =========================
async def build_dashboard(user_id: int, username: str):

    try:
        balance_rp = await get_balance(user_id)
        balance_rp = balance_rp or 0
    except Exception:
        balance_rp = 0

    kurs = await get_usd_rate() or 0
    balance_usd = float(balance_rp) * float(kurs)

    text = (
        "🔥 <b>DECODEFILEBOT</b>\n\n"
        f"👤 Username: @{username or 'user'}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Saldo: <b>Rp {balance_rp:,} / $ {balance_usd:,.4f}</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📌 DASHBOARD MENU\n"
        "━━━━━━━━━━━━━━"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Upfile", callback_data="upfile"),
            InlineKeyboardButton(text="📥 Getfile", callback_data="getfile"),
        ],
        [
            InlineKeyboardButton(text="💸 Withdraw", callback_data="withdraw"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistik", callback_data="statistik"),
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
        ],
    ])

    return text, keyboard


# =========================
# START COMMAND
# =========================
@router.message(F.text == "/start")
async def start(message: Message, bot: Bot):

    user = message.from_user
    user_id = user.id
    username = user.username or "NoUsername"

    try:
        await add_user(user_id, username, user.full_name)
    except Exception as e:
        print("ADD USER ERROR:", repr(e))

    # FORCE SUB CHANNEL
    if FORCE_CHANNEL:
        try:
            member = await bot.get_chat_member(FORCE_CHANNEL, user_id)

            if member.status not in ("member", "administrator", "creator"):
                return await message.answer(
                    "⚠️ AKSES DITOLAK\n\nJoin channel dulu sebelum pakai bot.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📢 Join Channel", url=FORCE_CHANNEL_LINK)],
                        [InlineKeyboardButton(text="✅ Sudah Join", callback_data="check_sub")]
                    ])
                )

        except Exception as e:
            print("FORCE SUB ERROR:", repr(e))

    text, keyboard = await build_dashboard(user_id, username)

    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# =========================
# HOME CALLBACK
# =========================
@router.callback_query(F.data == "home")
async def home(call: CallbackQuery):

    user = call.from_user
    user_id = user.id
    username = user.username or "NoUsername"

    try:
        text, keyboard = await build_dashboard(user_id, username)

        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        print("EDIT ERROR:", repr(e))

    await call.answer()

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
# TIMEZONE (WIB)
# =========================
WIB = timezone(timedelta(hours=7))
OPEN_HOUR = 9
CLOSE_HOUR = 20


def now_wib():
    return datetime.now(WIB)


def fmt_delta(td: timedelta):
    total = int(td.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}j {m}m {s}d"


def wd_status():
    now = now_wib()
    weekday = now.weekday()
    hour = now.hour

    if weekday >= 5:
        next_open = (now + timedelta(days=(7 - weekday))).replace(
            hour=OPEN_HOUR, minute=0, second=0, microsecond=0
        )
        return False, next_open, "⛔ WEEKEND CLOSED"

    if hour < OPEN_HOUR:
        next_open = now.replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
        return False, next_open, "⏳ BELUM BUKA"

    if hour >= CLOSE_HOUR:
        next_open = (now + timedelta(days=1)).replace(
            hour=OPEN_HOUR, minute=0, second=0, microsecond=0
        )
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        return False, next_open, "⛔ TUTUP"

    close_time = now.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0)
    return True, close_time, "🟢 OPEN"


# =========================
# KEYBOARD
# =========================
def withdraw_button(is_open: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟢 WITHDRAW OPEN" if is_open else "🔴 WITHDRAW CLOSED",
                callback_data="wd_open" if is_open else "wd_closed"
            )
        ],
        [InlineKeyboardButton("💸 REQUEST WITHDRAW", callback_data="wd_request")],
        [InlineKeyboardButton("🔙 KEMBALI", callback_data="home")]
    ])


# =========================
# STATE
# =========================
user_states = {}
live_tasks = {}


# =========================
# LIVE PANEL
# =========================
async def live_withdraw_panel(message, user_id):
    last_text = None

    try:
        for _ in range(120):
            open_status, _, status_text = wd_status()
            now = now_wib().strftime("%H:%M:%S")

            panel = (
                "💸 WITHDRAW CENTER\n\n"
                f"🕒 WIB: {now}\n"
                f"{status_text}\n\n"
                "━━━━━━━━━━━━━━"
            )

            if panel != last_text:
                await message.edit_text(panel, reply_markup=withdraw_button(open_status))
                last_text = panel

            await asyncio.sleep(5)

    except Exception as e:
        print("LIVE PANEL ERROR:", repr(e))

    finally:
        live_tasks.pop(user_id, None)


@router.callback_query(F.data == "wd_live")
async def wd_live(call: CallbackQuery):
    await call.answer()

    user_id = call.from_user.id

    task = live_tasks.get(user_id)
    if task and not task.done():
        task.cancel()

    live_tasks[user_id] = asyncio.create_task(
        live_withdraw_panel(call.message, user_id)
    )


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "wd_cancel")
async def wd_cancel(call: CallbackQuery):
    user_states.pop(call.from_user.id, None)
    await call.message.edit_text("❌ Withdraw dibatalkan")
    await call.answer()


# =========================
# WITHDRAW PAGE
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw_page(call: CallbackQuery):

    user_id = call.from_user.id

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT balance, wd_method, wd_provider, wd_name, wd_number
            FROM users WHERE user_id=$1
        """, user_id)

    if not row:
        return await call.message.edit_text("❌ User tidak ditemukan")

    open_status, _, _ = wd_status()

    text = (
        "💸 WITHDRAW CENTER\n\n"
        f"💰 Saldo: Rp {row['balance'] or 0:,}\n"
        f"📌 Status: {'🟢 OPEN' if open_status else '🔴 CLOSED'}\n\n"
        f"🏦 Method: {row['wd_method'] or '-'}\n"
        f"📱 Provider: {row['wd_provider'] or '-'}\n"
        f"👤 Nama: {row['wd_name'] or '-'}\n"
        f"📌 Nomor: {row['wd_number'] or '-'}\n\n"
        f"Min: Rp {MIN_WITHDRAW:,} | Max: Rp {MAX_WITHDRAW:,}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🔄 LIVE STATUS", callback_data="wd_live")],
        [InlineKeyboardButton("💸 REQUEST WITHDRAW", callback_data="wd_request")],
        [InlineKeyboardButton("🔙 HOME", callback_data="home")]
    ])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# =========================
# REQUEST WITHDRAW
# =========================
@router.callback_query(F.data == "wd_request")
async def wd_request(call: CallbackQuery):

    user_id = call.from_user.id
    state = user_states.setdefault(user_id, {})

    if state.get("lock"):
        return await call.answer("⛔ sedang diproses", show_alert=True)

    state["lock"] = True

    try:
        open_status, _, _ = wd_status()
        if not open_status:
            return await call.answer("🔴 Withdraw tutup", show_alert=True)

        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT balance, wd_method, wd_provider, wd_name, wd_number
                FROM users WHERE user_id=$1
            """, user_id)

            if not row:
                return await call.answer("❌ User tidak ditemukan", show_alert=True)

            if row["balance"] < MIN_WITHDRAW:
                return await call.answer("❌ saldo kurang", show_alert=True)

            await call.message.edit_text(
                f"💸 KONFIRMASI WITHDRAW\n\n"
                f"💰 Rp {row['balance']:,}\n\n"
                "Tekan CONFIRM",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton("🚀 CONFIRM", callback_data="wd_confirm")],
                    [InlineKeyboardButton("🔙 BACK", callback_data="withdraw")]
                ])
            )

    except Exception as e:
        print("WD REQUEST ERROR:", repr(e))

    finally:
        state.pop("lock", None)


# =========================
# CONFIRM WITHDRAW
# =========================
@router.callback_query(F.data == "wd_confirm")
async def wd_confirm(call: CallbackQuery):

    user_id = call.from_user.id
    state = user_states.setdefault(user_id, {})

    if state.get("lock"):
        return await call.answer("⛔ sedang diproses", show_alert=True)

    state["lock"] = True

    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():

                row = await conn.fetchrow("""
                    SELECT balance, wd_method, wd_provider, wd_name, wd_number
                    FROM users WHERE user_id=$1
                    FOR UPDATE
                """, user_id)

                if not row:
                    return await call.answer("❌ user not found")

                if not row["wd_name"] or not row["wd_number"]:
                    return await call.answer("❌ data belum lengkap")

                balance = row["balance"] or 0
                if balance < MIN_WITHDRAW:
                    return await call.answer("❌ saldo kurang")

                await conn.execute("""
                    INSERT INTO withdraws(
                        user_id, amount, fee, net_amount,
                        method, account_name, account_number, status
                    )
                    VALUES ($1,$2,0,$2,$3,$4,$5,'pending')
                """,
                user_id,
                balance,
                row["wd_method"],
                row["wd_name"],
                row["wd_number"]
                )

                await conn.execute("""
                    UPDATE users
                    SET balance=0,
                        total_withdraw=COALESCE(total_withdraw,0)+$1
                    WHERE user_id=$2
                """, balance, user_id)

        await call.message.edit_text(
            f"⏳ Withdraw pending\n💰 Rp {balance:,}\n"
        )

    except Exception as e:
        print("WD CONFIRM ERROR:", repr(e))

    finally:
        state.pop("lock", None)

# =========================
# STATE
# =========================

MAX_MEDIA = 100
MAX_SIZE = 2 * 1024 * 1024 * 1024

# =========================
# KEYBOARD
# =========================
def upload_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ DONE", callback_data="upload_done"),
            InlineKeyboardButton(text="❌ CANCEL", callback_data="upload_cancel")
        ]
    ])


def price_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 PAID", callback_data="price_paid")],
        [InlineKeyboardButton(text="🆓 FREE", callback_data="price_free")]
    ])


def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 SAVE", callback_data="upload_save"),
            InlineKeyboardButton(text="✏️ EDIT", callback_data="upload_edit")
        ]
    ])


# =========================
# CODE GEN
# =========================
def generate_code(v, p, d):
    rand = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    return f"bb_{v}v_{p}p_{d}d_{rand}"


# =========================
# START UPFILE
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery):

    uid = call.from_user.id

    upload_sessions[uid] = {
        "video": 0,
        "photo": 0,
        "document": 0,
        "items": [],
        "msg_id": call.message.message_id,
        "price": 0,
        "mode": "upload",
        "share": True,
        "processing": False
    }

    user_states[uid] = {"mode": "upload"}

    await call.message.edit_text(
        "📤 UPLOAD MODE AKTIF\nKirim media sekarang",
        reply_markup=upload_kb()
    )

    await call.answer()


# =========================
# MEDIA HANDLER
# =========================
@router.message(F.photo | F.video | F.document)
async def media_handler(message: Message):

    uid = message.from_user.id

    if user_states.get(uid, {}).get("mode") != "upload":
        return

    s = upload_sessions.get(uid)
    if not s:
        return

    file = message.photo[-1] if message.photo else message.video or message.document
    ftype = "photo" if message.photo else "video" if message.video else "document"
    size = getattr(file, "file_size", 0)

    if len(s["items"]) >= MAX_MEDIA:
        return await message.delete()

    if sum(x["size"] for x in s["items"]) + size > MAX_SIZE:
        return await message.delete()

    s[ftype] += 1
    s["items"].append({
        "file_id": file.file_id,
        "type": ftype,
        "size": size
    })

    v, p, d = s["video"], s["photo"], s["document"]
    total = len(s["items"])

    progress = int(total / MAX_MEDIA * 100)
    bar = "█" * (progress // 10) + "░" * (10 - (progress // 10))

    size_mb = round(sum(x["size"] for x in s["items"]) / 1024 / 1024, 2)

    text = (
        f"📤 UPLOAD PROGRESS\n\n"
        f"{bar} {progress}%\n"
        f"🎬 {v} | 🖼 {p} | 📄 {d} (total {total})\n"
        f"💾 {size_mb} MB"
    )

    now = time.time()
    if now - last_edit_time.get(uid, 0) < 1.2:
        return
    last_edit_time[uid] = now

    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=s["msg_id"],
            text=text,
            reply_markup=upload_kb()
        )
    except:
        pass

    await message.delete()


# =========================
# DONE → PRICE
# =========================
@router.callback_query(F.data == "upload_done")
async def done(call: CallbackQuery):

    uid = call.from_user.id
    s = upload_sessions.get(uid)

    if not s or not s["items"]:
        return await call.answer("Belum ada file", show_alert=True)

    user_states[uid] = {"mode": "price"}

    await call.message.edit_text("Pilih tipe:", reply_markup=price_kb())


# =========================
# FREE
# =========================
@router.callback_query(F.data == "price_free")
async def price_free(call: CallbackQuery):

    uid = call.from_user.id
    s = upload_sessions[uid]

    s["price"] = 0
    user_states[uid] = {"mode": "review"}

    await show_review(call, uid)


# =========================
# PAID
# =========================
@router.callback_query(F.data == "price_paid")
async def price_paid(call: CallbackQuery):

    uid = call.from_user.id
    user_states[uid] = {"mode": "set_price"}

    await call.message.edit_text("Masukkan harga (min 1000)")


# =========================
# SET PRICE
# =========================
@router.message(F.text)
async def set_price(message: Message):

    uid = message.from_user.id

    if user_states.get(uid, {}).get("mode") != "set_price":
        return

    s = upload_sessions.get(uid)

    try:
        price = int(message.text)
    except:
        return await message.answer("Angka tidak valid")

    if price < 1000:
        return await message.answer("Minimal 1000")

    s["price"] = price
    user_states[uid] = {"mode": "review"}

    await show_review(message, uid)


# =========================
# REVIEW
# =========================
async def show_review(event, uid):

    s = upload_sessions[uid]
    v, p, d = s["video"], s["photo"], s["document"]
    total = len(s["items"])

    text = (
        f"📦 REVIEW\n\n"
        f"🎬 {v} | 🖼 {p} | 📄 {d} (total {total})\n"
        f"💰 Price: {s['price']}"
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=review_kb())
    else:
        await event.answer(text)


# =========================
# EDIT (BACK TO UPLOAD)
# =========================
@router.callback_query(F.data == "upload_edit")
async def edit(call: CallbackQuery):

    uid = call.from_user.id

    user_states[uid] = {"mode": "upload"}

    await call.message.edit_text(
        "📤 Lanjut upload media...",
        reply_markup=upload_kb()
    )

# =========================
# BAYARGG CREATE INVOICE (REAL)
# =========================
async def create_bayargg_invoice(amount: int, code: str, uid: int):
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"{BAYARGG_URL}/api/invoice/create",
            headers={
                "Authorization": f"Bearer {BAYARGG_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "amount": amount,
                "reference": code,
                "customer_id": uid,
                "callback_url": "https://satpambot-production.up.railway.app/bayargg-webhook"
            }
        )

    data = res.json()

    if not data.get("success"):
        raise Exception(f"QRIS ERROR: {data}")

    return data["data"]  # harus ada invoice_id + qr_url


# =========================
# SAVE FINAL (PRODUCTION REAL)
# =========================
@router.callback_query(F.data == "upload_save")
async def save(call: CallbackQuery):

    uid = call.from_user.id
    s = upload_sessions.get(uid)

    if not s:
        return await call.answer("Session tidak ditemukan")

    if s.get("processing"):
        return await call.answer("Processing...")

    s["processing"] = True

    # =========================
    # GENERATE CODE STABLE
    # =========================
    code = generate_code(s["video"], s["photo"], s["document"])

    total = len(s["items"])
    size = sum(i["size"] for i in s["items"])
    now = datetime.utcnow().isoformat()

    # =========================
    # 1. SAVE TO SUPABASE (PERMANENT)
    # =========================
    supabase.table("uploads").insert({
        "code": code,
        "owner_id": uid,
        "video": s["video"],
        "photo": s["photo"],
        "document": s["document"],
        "total_media": total,
        "total_size": size,
        "price": s["price"],
        "share": s["share"],
        "created_at": now,
        "status": "active",
        "payment_status": "free" if s["price"] == 0 else "pending"
    }).execute()

    # =========================
    # 2. SAVE MEDIA LIST
    # =========================
    supabase.table("media_files").insert([
        {
            "code": code,
            "file_id": i["file_id"],
            "file_type": i["type"],
            "file_size": i["size"]
        }
        for i in s["items"]
    ]).execute()

    # =========================
    # 3. QRIS REAL (BAYARGG)
    # =========================
    invoice_id = None
    qr_url = None

    if s["price"] > 0:

        invoice = await create_bayargg_invoice(
            amount=s["price"],
            code=code,
            uid=uid
        )

        invoice_id = invoice["invoice_id"]
        qr_url = invoice.get("qr_url")

        # update DB dengan invoice real
        supabase.table("uploads").update({
            "invoice_id": invoice_id,
            "qr_url": qr_url
        }).eq("code", code).execute()

    # =========================
    # FINAL MESSAGE
    # =========================
    await call.message.edit_text(
        "✅ <b>UPLOAD CREATED</b>\n\n"
        f"🔑 Code: <code>{code}</code>\n"
        f"📁 Total: {total} media\n"
        f"💾 Size: {round(size/1024/1024,2)} MB\n"
        f"💰 Price: {s['price']}\n"
        f"📡 Share: {'YES' if s['share'] else 'NO'}\n"
        f"🧾 Invoice: {invoice_id or 'FREE'}\n\n"
        "⚡ Code ini TETAP VALID walau bot restart / pindah server",
        parse_mode="HTML"
    )

    # =========================
    # CLEAN LOCAL SESSION ONLY
    # =========================
    upload_sessions.pop(uid, None)
    user_states.pop(uid, None)
    last_edit_time.pop(uid, None)

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
                SELECT file_id, file_type, is_paid, price
                FROM medias
                WHERE code=$1
                ORDER BY id ASC
            """, code)
    except Exception as e:
        print("DB ERROR:", e)
        return []
    return rows

# =========================
# CHECK PAYMENT
# =========================
async def check_paid(conn, user_id: int, code: str):
    return await conn.fetchval("""
        SELECT 1 FROM payments
        WHERE user_id=$1 AND code=$2 AND status='PAID'
        LIMIT 1
    """, user_id, code)

# =========================
# GETFILE START
# =========================
@router.callback_query(F.data == "getfile")
async def start_get(call: CallbackQuery):
    user_id = call.from_user.id
    user_states[user_id] = {"mode": "getfile", "step": "input_code"}
    await call.message.edit_text("📥 Kirim CODE media kamu")
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

    code = message.text.strip()

    # =========================
    # LOAD DATA DARI DB
    # =========================
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT file_id, file_type, is_paid, price
            FROM medias
            WHERE code=$1
            ORDER BY id ASC
        """, code)

        if not rows:
            return await message.answer("❌ Code tidak ditemukan")

        is_paid = any(r["is_paid"] for r in rows)
        price = rows[0]["price"] if is_paid else 0

        # =========================
        # CEK AKSES (FREE / PAID)
        # =========================
        if not has_access(user_id, code):

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"💳 PAY NOW ({price})",
                        callback_data=f"pay:{code}"
                    )
                ]
            ])

            return await message.answer(
                f"🔒 CODE BERBAYAR\n💰 Harga: {price}\n\nSilahkan bayar dulu untuk akses file ini.",
                reply_markup=kb
            )

    # =========================
    # SET DATA (SUDAH BISA AKSES)
    # =========================
    data = [
        {
            "file_id": r["file_id"],
            "file_type": normalize_type(r["file_type"])
        }
        for r in rows
    ]

    user_states[user_id] = {
        "mode": "view",
        "code": code,
        "page": 0,
        "page_size": 10,
        "data": data,
        "last_panel_msg": None
    }

    page_history[user_id] = set()

    await message.answer(f"📦 Total file: {len(data)}")

    await render_page(user_id, message.bot, message.chat.id)

# =========================
# PAYMENT BUTTON
# =========================
@router.callback_query(F.data.startswith("pay:"))
async def pay(call: CallbackQuery):
    code = call.data.split(":")[1]
    user_id = call.from_user.id
    async with db_pool.acquire() as conn:
        price = await conn.fetchval("SELECT price FROM medias WHERE code=$1 LIMIT 1", code)
    qr_url = f"https://qr-gateway.com/qr?code={code}&user={user_id}&amount={price}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 OPEN QR PAYMENT", url=qr_url)],
        [InlineKeyboardButton(text="🔄 CHECK PAYMENT", callback_data=f"checkpay:{code}")]
    ])
    await call.message.edit_text(
        f"💳 PAYMENT REQUIRED\nCODE: `{code}`\nPRICE: {price}",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("confirm:"))
async def confirm(call: CallbackQuery):

    user_id = call.from_user.id
    code = call.data.split(":")[1]

    # unlock user untuk code ini
    paid_users[code].add(user_id)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT file_id, file_type
            FROM medias
            WHERE code=$1
            ORDER BY id ASC
        """, code)

    data = [
        {
            "file_id": r["file_id"],
            "file_type": normalize_type(r["file_type"])
        }
        for r in rows
    ]

    user_states[user_id] = {
        "mode": "view",
        "code": code,
        "page": 0,
        "page_size": 10,
        "data": data,
        "last_panel_msg": None
    }

    page_history[user_id] = set()

    await call.message.edit_text("✅ PAYMENT SUCCESS\n📦 Loading media...")

    await render_page(user_id, call.bot, call.message.chat.id)

    await call.answer("Unlocked ✅")

# =========================
# CHECK PAYMENT
# =========================
@router.callback_query(F.data.startswith("checkpay:"))
async def check_pay(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]
    async with db_pool.acquire() as conn:
        paid = await conn.fetchval("SELECT 1 FROM payments WHERE user_id=$1 AND code=$2 AND status='PAID'", user_id, code)
        if not paid:
            return await call.answer("❌ Belum bayar", show_alert=True)
        rows = await conn.fetch("SELECT file_id, file_type FROM medias WHERE code=$1 ORDER BY id ASC", code)
    data = [{"file_id": r["file_id"], "file_type": normalize_type(r["file_type"])} for r in rows]
    user_states[user_id] = {"mode": "view", "code": code, "page": 0, "page_size": 10, "data": data, "last_panel_msg": None}
    await call.message.edit_text("✅ PAYMENT VERIFIED\n📦 Loading media...")
    await render_page(user_id, call.bot, call.message.chat.id)

# =========================
# RENDER PAGE + PAGINATION
# =========================
async def render_page(user_id: int, bot, chat_id: int):
    state = user_states.get(user_id)
    if not state:
        return
    data = state["data"]
    page = state.get("page", 0)
    size = state.get("page_size", 10)
    total_pages = max(1, (len(data) + size - 1) // size)
    page = max(0, min(page, total_pages - 1))
    state["page"] = page
    start = page * size
    end = start + size
    chunk = data[start:end]

    # SEND MEDIA
    media = []
    for m in chunk[:10]:
        if m["file_type"] == "photo":
            media.append(InputMediaPhoto(media=m["file_id"]))
        elif m["file_type"] == "video":
            media.append(InputMediaVideo(media=m["file_id"]))
        else:
            media.append(InputMediaDocument(media=m["file_id"]))
    if media:
        await bot.send_media_group(chat_id, media)

    # KEYBOARD
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅ Prev", callback_data="prev"),
            InlineKeyboardButton(text="➡ Next", callback_data="next")
        ],
        [InlineKeyboardButton(text="📢 Channel", url="https://t.me/yourchannel")]
    ])
    text = f"📦 Page {page+1}/{total_pages}"
    await bot.send_message(chat_id, text, reply_markup=kb)

# =========================
# PAGINATION HANDLER
# =========================
@router.callback_query(F.data.in_(["next", "prev"]))
async def pagination(call: CallbackQuery):
    user_id = call.from_user.id
    async with pagination_lock[user_id]:
        state = user_states.get(user_id)
        if not state: return await call.answer("Session expired", show_alert=True)
        data = state.get("data") or []
        if not data: return await call.answer("No data", show_alert=True)
        old_page = state.get("page", 0)
        size = state.get("page_size", 10)
        max_page = (len(data)-1)//size
        page = old_page
        if call.data=="next": page+=1
        elif call.data=="prev": page-=1
        page = max(0, min(page, max_page))
        if page==old_page: return await call.answer()
        state["page"] = page
        await render_page(user_id, call.bot, call.message.chat.id)
        await call.answer()
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
