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
from datetime import datetime
from collections import defaultdict

# =========================
# THIRD PARTY
# =========================
import asyncpg
import httpx
import uvicorn
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException

from aiogram import Bot, Router, F
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

            rate = data["rates"]["USD"]

            USD_RATE_CACHE["rate"] = rate
            USD_RATE_CACHE["last_update"] = now

            return rate

    except Exception as e:
        print("USD RATE ERROR:", repr(e))
        return USD_RATE_CACHE["rate"]


# =========================
# DASHBOARD BUILDER (FIXED)
# =========================
async def build_dashboard(user_id: int, username: str):

    try:
        balance_rp = await get_balance(user_id)
    except:
        balance_rp = 0

    kurs = await get_usd_rate()

    balance_usd = balance_rp * kurs

    text = (
        "🔥 <b>DECODEFILEBOT</b>\n\n"
        f"👤 Username: @{username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"💰 Saldo: <b>Rp {balance_rp:,} / $ {balance_usd:,.4f}</b>\n\n"
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
    username = user.username or "NoUsername"

    try:
        await add_user(user_id, username, user.full_name)
    except Exception as e:
        print("ADD USER ERROR:", repr(e))

    # force join
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
            print("FORCE SUB ERROR:", repr(e))

    text, keyboard = await build_dashboard(user_id, username)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


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
# CONFIG
# =========================

IDR_TO_USD = 16000

def idr_to_usd(idr: int) -> float:
    try:
        return round(idr / IDR_TO_USD, 2)
    except:
        return 0.0


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


# =========================
# FORMAT DELTA
# =========================
def fmt_delta(td: timedelta):
    total = int(td.total_seconds())
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h}j {m}m {s}d"


# =========================
# WITHDRAW STATUS
# =========================
def wd_status():
    now = now_wib()
    weekday = now.weekday()
    hour = now.hour

    if weekday >= 5:
        next_open = (now + timedelta(days=(7 - weekday))).replace(
            hour=OPEN_HOUR, minute=0, second=0, microsecond=0
        )
        return False, next_open, f"⛔ WEEKEND CLOSED\n🕘 Buka lagi dalam {fmt_delta(next_open - now)}"

    if hour < OPEN_HOUR:
        next_open = now.replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
        return False, next_open, f"⏳ BELUM BUKA\n🕘 Buka dalam {fmt_delta(next_open - now)}"

    if hour >= CLOSE_HOUR:
        next_open = (now + timedelta(days=1)).replace(
            hour=OPEN_HOUR, minute=0, second=0, microsecond=0
        )
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        return False, next_open, f"⛔ TUTUP\n🕘 Buka lagi dalam {fmt_delta(next_open - now)}"

    close_time = now.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0)
    return True, close_time, f"🟢 OPEN\n⏳ Tutup dalam {fmt_delta(close_time - now)}"


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
# STATE STORAGE
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
            open_status, _, text_status = wd_status()
            now = now_wib().strftime("%H:%M:%S")

            panel = (
                "💸 WITHDRAW CENTER\n\n"
                f"🕒 WIB: {now}\n\n"
                f"{text_status}\n\n"
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
# CANCEL HANDLER (FIX MISSING)
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
        await conn.execute("""
            INSERT INTO users (user_id, balance)
            VALUES ($1, 0)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id)

        row = await conn.fetchrow("""
            SELECT balance, wd_method, wd_provider, wd_name, wd_number
            FROM users WHERE user_id=$1
        """, user_id)

    if not row:
        return await call.message.edit_text("❌ User tidak ditemukan")

    open_status, _, _ = wd_status()

    text = (
        "💸 <b>WITHDRAW CENTER</b>\n\n"
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
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data="wd_settings")],
        [InlineKeyboardButton("🔙 HOME", callback_data="home")]
    ])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


# =========================
# REQUEST WITHDRAW HANDLER
# =========================
@router.callback_query(F.data == "wd_request")
async def wd_request(call: CallbackQuery):
    user_id = call.from_user.id
    state = user_states.setdefault(user_id, {})

    # LOCK agar tidak double click
    if state.get("wd_block"):
        return await call.answer("⛔ Withdraw sedang diproses", show_alert=True)
    state["wd_block"] = True

    try:
        # cek sistem buka/tutup
        open_status, _, _ = wd_status()
        if not open_status:
            return await call.answer("🔴 Withdraw tutup", show_alert=True)

        async with db_pool.acquire() as conn:
            # ambil data user
            row = await conn.fetchrow("""
                SELECT balance, wd_method, wd_provider, wd_name, wd_number
                FROM users WHERE user_id=$1
            """, user_id)

            if not row:
                return await call.answer("❌ User tidak ditemukan", show_alert=True)

            balance = row["balance"] or 0
            if balance < MIN_WITHDRAW:
                return await call.answer(f"❌ Saldo minimal Rp {MIN_WITHDRAW:,}", show_alert=True)

            # tampilkan konfirmasi withdraw
            await call.message.edit_text(
                "💸 KONFIRMASI WITHDRAW\n\n"
                f"💰 Saldo saat ini: Rp {balance:,}\n"
                f"🏦 Method: {row['wd_method']} ({row['wd_provider']})\n\n"
                "Tekan 🚀 CONFIRM untuk melanjutkan",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton("🚀 CONFIRM", callback_data="wd_confirm")],
                    [InlineKeyboardButton("🔙 BACK", callback_data="withdraw")]
                ])
            )

    except Exception as e:
        print("WD_REQUEST ERROR:", repr(e))
        await call.answer("❌ Terjadi kesalahan", show_alert=True)

    finally:
        state.pop("wd_block", None)


# =========================
# CONFIRM / EXECUTE WITHDRAW
# =========================
@router.callback_query(F.data == "wd_confirm")
async def wd_confirm(call: CallbackQuery):
    user_id = call.from_user.id
    state = user_states.setdefault(user_id, {})

    # LOCK agar tidak double click
    if state.get("wd_block"):
        return await call.answer("⛔ Withdraw sedang diproses", show_alert=True)
    state["wd_block"] = True

    try:
        async with db_pool.acquire() as conn:
            # ambil saldo + pending withdraw
            row = await conn.fetchrow("""
                SELECT balance, wd_method, wd_provider, wd_name, wd_number,
                    COALESCE((
                        SELECT SUM(amount) FROM withdraws
                        WHERE user_id=$1 AND status='pending'
                    ),0) AS pending_total
                FROM users WHERE user_id=$1
            """, user_id)

            if not row:
                return await call.answer("❌ User tidak ditemukan", show_alert=True)

            if not row["wd_method"] or not row["wd_name"] or not row["wd_number"]:
                return await call.answer("❌ Data withdraw belum lengkap", show_alert=True)

            balance = row["balance"] or 0
            pending = row["pending_total"]
            total_wd = balance + pending

            if total_wd < MIN_WITHDRAW:
                return await call.answer(
                    f"❌ Total saldo ({total_wd:,}) belum cukup",
                    show_alert=True
                )

            # 🔥 Insert withdraw baru (hanya saldo baru, pending tetap)
            if balance > 0:
                await conn.execute("""
                    INSERT INTO withdraws(
                        user_id, amount, fee, net_amount,
                        method, account_name, account_number, status
                    )
                    VALUES($1,$2,0,$2,$3,$4,$5,'pending')
                """,
                user_id,
                balance,
                row["wd_method"],
                row["wd_name"],
                row["wd_number"]
                )

                # reset saldo
                await conn.execute("""
                    UPDATE users
                    SET balance=0,
                        total_withdraw=COALESCE(total_withdraw,0)+$1
                    WHERE user_id=$2
                """, balance, user_id)

        await call.message.edit_text(
            f"⏳ Withdraw pending\n💰 Total pending saat ini: Rp {total_wd:,}\n"
            "⚠️ Admin akan memproses manual"
        )

    except Exception as e:
        print("WD_CONFIRM ERROR:", repr(e))
        await call.answer("❌ Terjadi kesalahan", show_alert=True)

    finally:
        state.pop("wd_block", None)


# =========================
# ADMIN NOTIFY SUCCESS FUNCTION
# =========================
async def notify_withdraw_success(user_id: int, amount: int, method: str, provider: str, name: str, number: str):
    try:
        await bot.send_message(
            user_id,
            f"✅ Withdraw SUKSES!\n\n"
            f"💰 Total diterima: Rp {amount:,}\n"
            f"🏦 {method} ({provider})\n"
            f"👤 {name}\n"
            f"📌 {number}"
        )
    except Exception as e:
        print("NOTIFY WD SUCCESS ERROR:", repr(e))
        
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
async def handle_price_input(message: Message):

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
