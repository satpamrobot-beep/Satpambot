# =========================
# IMPORT
# =========================

# Standard Library
import os
import re
import time
import json
import hmac
import hashlib
import random
import secrets
import string
import asyncio
from datetime import datetime, timedelta

# Third Party
import httpx
import asyncpg
import uvicorn
from dotenv import load_dotenv

from fastapi import FastAPI, Request

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
    InputMediaDocument,
)

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramRetryAfter
)

# =========================
# LOAD ENV
# =========================

load_dotenv()

# =========================
# CORE CONFIG
# =========================

def get_env(name: str, required: bool = True, default: str = "") -> str:
    value = os.getenv(name, default).strip()

    if required and not value:
        raise RuntimeError(f"{name} tidak ditemukan")

    return value


BOT_TOKEN = get_env("BOT_TOKEN")
DATABASE_URL = get_env("DATABASE_URL")
CHANNEL_DB = get_env("CHANNEL_DB", required=False)

# =========================
# PAYMENT CONFIG
# =========================

PAYGG_SECRET = get_env("PAYGG_SECRET", required=False)
PAYGG_API_KEY = get_env("PAYGG_API_KEY", required=False)

# =========================
# OPTIONAL CONFIG
# =========================

UPDATE_CHANNEL = get_env("UPDATE_CHANNEL", required=False)
VIP_LINK = get_env("VIP_LINK", required=False)

# =========================
# SAFE ENV PARSER
# =========================

def get_int_env(name: str, default: int = 0) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


NOTIFICATION_CHANNEL = get_int_env("NOTIFICATION_CHANNEL")

# =========================
# ADMINS
# =========================

ADMINS: set[int] = set()

_raw_admins = os.getenv("ADMINS", "")

if _raw_admins:
    for admin_id in _raw_admins.split(","):
        admin_id = admin_id.strip()

        if admin_id.isdigit():
            ADMINS.add(int(admin_id))

# =========================
# GLOBAL OBJECT (SAFE INIT)
# =========================

bot: Bot | None = None
dp: Dispatcher | None = None
router = Router()

# =========================
# HELPERS
# =========================

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS


def generate_code(length: int = 10) -> str:
    chars = string.ascii_uppercase + string.digits

    return "".join(
        secrets.choice(chars)
        for _ in range(length)
    )


def generate_order_id() -> str:
    return (
        "INV-"
        + datetime.now().strftime("%Y%m%d")
        + "-"
        + secrets.token_hex(4).upper()
    )


def rupiah(amount: int) -> str:
    return f"Rp {amount:,}".replace(",", ".")

# =========================
# DATABASE
# =========================

db_pool: asyncpg.Pool | None = None


async def init_db():
    global db_pool

    if db_pool is not None:
        return

    try:
        db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )

        async with db_pool.acquire() as conn:

            # =========================
            # USERS
            # =========================
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                fullname TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

            # =========================
            # WALLETS
            # =========================
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS wallets(
                user_id BIGINT PRIMARY KEY,
                saldo BIGINT DEFAULT 0,
                total_pending BIGINT DEFAULT 0,
                total_process BIGINT DEFAULT 0,
                total_failed BIGINT DEFAULT 0,
                total_success BIGINT DEFAULT 0
            )
            """)

            # =========================
            # CODES
            # =========================
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS codes(
                id SERIAL PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                owner_id BIGINT,
                buyer_id BIGINT,
                price BIGINT DEFAULT 0,
                is_paid BOOLEAN DEFAULT FALSE,
                total_media INTEGER DEFAULT 0,
                total_size BIGINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_codes_code ON codes(code)")

            # =========================
            # MEDIAS
            # =========================
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS medias(
                id SERIAL PRIMARY KEY,
                code TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size BIGINT DEFAULT 0
            )
            """)

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_medias_code ON medias(code)")

            # =========================
            # TRANSACTIONS (ANTI ERROR)
            # =========================
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions(
                id SERIAL PRIMARY KEY,
                order_id TEXT UNIQUE NOT NULL
            )
            """)

            # 🔥 AUTO MIGRATION
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS user_id BIGINT")
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS code TEXT")
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS amount BIGINT DEFAULT 0")
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS fee BIGINT DEFAULT 0")
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS net BIGINT DEFAULT 0")
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'")
            await conn.execute("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()")

            # 🔥 INDEX
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_tx_order ON transactions(order_id)")

            # =========================
            # PAYMENTS
            # =========================
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS payments(
                id SERIAL PRIMARY KEY,
                order_id TEXT UNIQUE,
                user_id BIGINT,
                code TEXT,
                amount BIGINT,
                status TEXT DEFAULT 'pending',
                message_id BIGINT,
                group_message_id BIGINT,
                expires_at TIMESTAMP
            )
            """)

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id)")

        print("✅ Database Ready")

    except Exception as e:
        print(f"❌ Database Error: {e}")
        raise
# =========================
# CACHE / MEMORY
# =========================

from collections import defaultdict
from asyncio import Lock

cooldown = {
    "global": {},
    "page": {},
}

page_history: dict[int, list] = {}
page_cooldown: dict[int, float] = {}

user_click_lock: dict[int, Lock] = {}
upload_sessions: dict[int, dict] = {}
user_states: dict[int, str] = {}

last_edit_time: dict[int, float] = {}
user_last_action: dict[int, float] = {}

force_cache: dict[int, bool] = {}

broadcast_running: bool = False
payment_cache: dict[str, dict] = {}

# LOCK (SAFE VERSION)
user_upload_lock: dict[int, Lock] = {}
user_download_lock: dict[int, Lock] = {}

# =========================
# APP
# =========================

app = FastAPI()

# =========================
# ANTI SPAM + RATE LIMIT
# =========================

GLOBAL_DELAY = 0.08
USER_DELAY = 1.5

last_global_send = 0.0
global_lock = Lock()


def user_limit(user_id: int) -> bool:
    now = time.time()

    last = user_last_action.get(user_id, 0)

    if now - last < USER_DELAY:
        return False

    user_last_action[user_id] = now
    return True


async def global_throttle():
    global last_global_send

    async with global_lock:
        now = time.time()

        if now - last_global_send < GLOBAL_DELAY:
            await asyncio.sleep(
                GLOBAL_DELAY - (now - last_global_send)
            )

        last_global_send = time.time()


async def safe_send(func, *args, **kwargs):
    for attempt in range(5):
        try:
            await global_throttle()
            return await func(*args, **kwargs)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

        except TelegramBadRequest as e:
            print(f"[BAD_REQUEST] {e}")
            return None

        except Exception as e:
            print(f"[ERROR {attempt + 1}] {e}")
            await asyncio.sleep(attempt + 1)

    return None


# =========================
# LOCK HELPERS
# =========================

def get_user_lock(lock_dict: dict[int, Lock], user_id: int) -> Lock:
    if user_id not in lock_dict:
        lock_dict[user_id] = Lock()
    return lock_dict[user_id]


# =========================
# ROUTER
# =========================

# ⚠️ JANGAN DUPLIKAT!
# router sudah dibuat di atas (config section)

# =========================
# KEYBOARD
# =========================

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


MAIN_MENU = [
    ["📤 Up File", "📥 Get File"],
    ["💰 Wallet", "🧾 Invoice"],
    ["📊 Account", "💸 Withdraw"],
    ["🔔 Status", "⭐ VIP"],
]


def get_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=btn) for btn in row]
            for row in MAIN_MENU
        ],
        resize_keyboard=True,
        input_field_placeholder="Upload / ambil file / cek wallet... 💸"
    )

# =========================
# VERIFY SIGNATURE
# =========================

def verify_signature(raw_body: bytes, signature: str) -> bool:
    if not PAYGG_SECRET:
        return True

    expected = hmac.new(
        PAYGG_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature or "")


# =========================
# CREATE QRIS
# =========================

async def create_qris(order_id: str, amount: int):
    expires_at = datetime.now() + timedelta(minutes=5)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.paygg.example/create-invoice",
                headers={
                    "Authorization": f"Bearer {PAYGG_API_KEY}"
                },
                json={
                    "order_id": order_id,
                    "amount": amount,
                    "method": "qris",
                    "expired_at": expires_at.isoformat()
                }
            )

            response.raise_for_status()
            data = response.json()

    except Exception as e:
        print("[QR CREATE ERROR]", e)
        return None

    return {
        "order_id": order_id,
        "qr_url": data.get("qr_url"),
        "expires_at": expires_at
    }


# =========================
# SEND QR
# =========================

async def send_qr(user_id: int, qr_url: str, caption: str) -> int:
    if not bot:
        return 0

    msg = await safe_send(
        bot.send_photo,
        chat_id=user_id,
        photo=qr_url,
        caption=caption
    )

    return msg.message_id if msg else 0


# =========================
# QR EXPIRE WATCHER
# =========================

async def qr_expire_watcher():
    while True:
        try:
            async with db_pool.acquire() as conn:

                rows = await conn.fetch("""
                    SELECT order_id, user_id, message_id
                    FROM payments
                    WHERE status='pending'
                    AND expires_at < NOW()
                """)

                for row in rows:

                    if bot:
                        try:
                            await bot.delete_message(
                                row["user_id"],
                                row["message_id"]
                            )
                        except Exception:
                            pass

                    await conn.execute("""
                        UPDATE payments
                        SET status='expired'
                        WHERE order_id=$1
                    """, row["order_id"])

        except Exception as e:
            print("[QR WATCHER]", e)

        await asyncio.sleep(10)


# =========================
# WEBHOOK
# =========================

@app.post("/webhook")
async def webhook(request: Request):

    raw_body = await request.body()

    try:
        data = json.loads(raw_body)
    except Exception:
        return {"ok": False}

    signature = request.headers.get("X-Signature", "")

    if not verify_signature(raw_body, signature):
        return {"ok": False, "error": "invalid_signature"}

    order_id = data.get("order_id")
    status = data.get("status")
    amount = int(data.get("amount") or 0)

    if not order_id:
        return {"ok": False}

    if status not in ("paid", "failed", "expired"):
        return {"ok": True}

    user_id = None
    code = None
    msg_id = None
    qr_message_id = None

    async with db_pool.acquire() as conn:
        async with conn.transaction():

            payment = await conn.fetchrow("""
                SELECT *
                FROM payments
                WHERE order_id=$1
                FOR UPDATE
            """, order_id)

            if not payment:
                return {"ok": False}

            # 🔒 HARD LOCK STATUS
            if payment["status"] in ("paid", "failed", "expired"):
                return {"ok": True}

            user_id = payment["user_id"]
            code = payment["code"]
            msg_id = payment["group_message_id"]
            qr_message_id = payment["message_id"]

            await conn.execute("""
                UPDATE payments
                SET status=$1
                WHERE order_id=$2
            """, status, order_id)

            if status == "paid":
                await conn.execute("""
                    UPDATE wallets
                    SET
                        saldo = saldo + $1,
                        total_success = total_success + $1
                    WHERE user_id = $2
                """, amount, user_id)

    # =========================
    # CHANNEL UPDATE
    # =========================

    if msg_id and NOTIFICATION_CHANNEL and bot:
        try:
            icon = {
                "paid": "🟢 SUCCESS",
                "failed": "🔴 FAILED",
                "expired": "⚫ EXPIRED"
            }.get(status, "🟡 PROCESS")

            await safe_send(
                bot.edit_message_text,
                chat_id=NOTIFICATION_CHANNEL,
                message_id=msg_id,
                text=f"{icon}\n\nUser : {user_id}\nCode : {code}"
            )

        except Exception as e:
            print("[CHANNEL UPDATE]", e)

    # =========================
    # USER ACTION
    # =========================

    try:
        if not bot:
            return {"ok": True}

        if status == "paid":

            if qr_message_id:
                try:
                    await bot.delete_message(user_id, qr_message_id)
                except Exception:
                    pass

            async with db_pool.acquire() as conn:
                medias = await conn.fetch("""
                    SELECT file_id, file_type
                    FROM medias
                    WHERE code=$1
                """, code)

            for media in medias:

                if media["file_type"] == "photo":
                    await safe_send(bot.send_photo, user_id, media["file_id"])

                elif media["file_type"] == "video":
                    await safe_send(bot.send_video, user_id, media["file_id"])

                else:
                    await safe_send(bot.send_document, user_id, media["file_id"])

                await asyncio.sleep(0.05)  # 🔥 anti flood

            await safe_send(
                bot.send_message,
                user_id,
                f"🟢 Pembayaran berhasil\n\nCode: {code}"
            )

        elif status == "expired":

            if qr_message_id:
                try:
                    await bot.delete_message(user_id, qr_message_id)
                except Exception:
                    pass

            await safe_send(
                bot.send_message,
                user_id,
                "⚫ QRIS EXPIRED"
            )

    except Exception as e:
        print("[USER ACTION]", e)

    return {"ok": True}

# =========================
# CONFIG FORCE SUB
# =========================

FORCE_CHANNEL = -1003712587847
FORCE_CHANNEL_LINK = "https://t.me/+3g_yhHwxCrc5ZTg9"


# =========================
# CHECK FORCE SUB
# =========================

async def check_force_sub(bot: Bot, user_id: int, channel: int = FORCE_CHANNEL) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=channel,
            user_id=user_id
        )

        return member.status in ("member", "administrator", "creator")

    except Exception as e:
        print(f"[FORCE_SUB ERROR] {e}")

        # 🔥 fallback (anggap belum join biar aman)
        return False


# =========================
# FORCE SUB KEYBOARD
# =========================

def force_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Join Channel",
                    url=FORCE_CHANNEL_LINK
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Saya Sudah Join",
                    callback_data="check_sub"
                )
            ]
        ]
    )


# =========================
# FORCE SUB GUARD (REUSABLE)
# =========================

async def force_sub_guard(message: Message, bot: Bot) -> bool:
    user = message.from_user
    if not user:
        return False

    if not FORCE_CHANNEL:
        return True

    joined = await check_force_sub(bot, user.id, FORCE_CHANNEL)

    if not joined:
        await safe_send(
            message.answer,
            (
                "🚫 <b>AKSES DITOLAK</b>\n\n"
                "😏 Kamu belum join channel.\n"
                "Join dulu baru bisa pakai bot.\n\n"
                "👇 Tekan tombol di bawah"
            ),
            parse_mode="HTML",
            reply_markup=force_kb()
        )
        return False

    return True


# =========================
# START
# =========================

@router.message(CommandStart())
async def start(message: Message, bot: Bot):

    user = message.from_user
    if not user:
        return

    # SAVE USER
    try:
        await add_user(
            user.id,
            user.username or "ghost",
            user.full_name
        )
    except Exception as e:
        print("[ADD USER ERROR]", e)

    # ANTI SPAM
    if not user_limit(user.id):
        return await safe_send(
            message.answer,
            "⏳ Santai dulu bos… jangan spam 😏"
        )

    # 🔥 FORCE SUB CHECK (pakai guard)
    if not await force_sub_guard(message, bot):
        return

    # MAIN MENU
    await safe_send(
        message.answer,
        (
            "🔥 <b>FILE CODE SYSTEM</b>\n\n"
            "━━━━━━━━━━━━━━\n"
            "😈 STATUS : ONLINE\n"
            "━━━━━━━━━━━━━━\n\n"
            "📤 Upload File\n"
            "📥 Get File\n"
            "💰 Wallet\n"
            "📊 Account\n\n"
            "━━━━━━━━━━━━━━\n"
            "⚠️ PERINGATAN\n"
            "━━━━━━━━━━━━━━\n"
            "• Simpan code baik-baik\n"
            "• Salah code = file tidak ditemukan\n"
            "• Jangan bagikan code pribadi\n\n"
            "😏 Selamat menggunakan bot."
        ),
        parse_mode="HTML",
        reply_markup=get_keyboard()
    )


# =========================
# CHECK SUB
# =========================

@router.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery, bot: Bot):

    user_id = call.from_user.id

    if not user_limit(user_id):
        return await call.answer(
            "⏳ Pelan dikit...",
            show_alert=True
        )

    joined = await check_force_sub(bot, user_id, FORCE_CHANNEL)

    if not joined:
        return await call.answer(
            "🚫 Kamu belum join channel.",
            show_alert=True
        )

    # 🔥 edit message biar clean
    try:
        await call.message.edit_text(
            "✅ <b>VERIFIED</b>\n\n😈 Akses berhasil dibuka.",
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass
    except Exception as e:
        print("[CHECK SUB ERROR]", e)

    # kirim menu
    await safe_send(
        call.message.answer,
        (
            "🔥 <b>AKSES DIBUKA</b>\n\n"
            "😈 Verifikasi berhasil.\n"
            "Silakan gunakan bot."
        ),
        parse_mode="HTML",
        reply_markup=get_keyboard()
    )

    await call.answer("✅ Verified")

# =========================
# CONFIG
# =========================

GROUP_ID = -1003920865154


# =========================
# UPLOAD KEYBOARD
# =========================

def upload_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ DONE", callback_data="upload_done"),
                InlineKeyboardButton(text="❌ CANCEL", callback_data="upload_cancel")
            ]
        ]
    )


# =========================
# START UPLOAD
# =========================

@router.message(F.text == "📤 Up File")
async def up_file(message: Message, bot: Bot):

    user = message.from_user
    if not user:
        return

    user_id = user.id

    if not user_limit(user_id):
        return await safe_send(message.answer, "⏳ Jangan spam ya 😏")

    # 🔥 OPTIONAL: FORCE SUB
    if not await force_sub_guard(message, bot):
        return

    # 🔥 reset clean
    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    user_states[user_id] = {"mode": "upload"}

    upload_sessions[user_id] = {
        "video": 0,
        "photo": 0,
        "document": 0,
        "items": [],
        "msg_id": None,
        "created_at": time.time(),
        "locked": False,
        "processing": False,
        "step": None,
        "title": None,
        "paid": False,
        "price": 0,
        "share": False
    }

    msg = await safe_send(
        message.answer,
        (
            "📤 <b>UPLOAD MODE AKTIF</b>\n\n"
            "😏 Kirim file sekarang.\n"
            "Klik DONE jika sudah selesai."
        ),
        parse_mode="HTML",
        reply_markup=upload_kb()
    )

    if not msg:
        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        return

    upload_sessions[user_id]["msg_id"] = msg.message_id


# =========================
# MEDIA HANDLER
# =========================

@router.message(F.photo | F.video | F.document)
async def handle_media(message: Message):

    user_id = message.from_user.id

    if user_states.get(user_id, {}).get("mode") != "upload":
        return

    session = upload_sessions.get(user_id)
    if not session or not session.get("msg_id") or session.get("locked"):
        return

    # EXPIRE
    if time.time() - session["created_at"] > 1800:
        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        return await safe_send(message.answer, "⏰ Session expired.")

    # LIMIT
    if len(session["items"]) >= 100:
        return await safe_send(message.answer, "🚫 Maks 100 file.")

    # DETECT FILE
    file_obj, file_type = None, None

    if message.photo:
        file_obj = message.photo[-1]
        file_type = "photo"
        session["photo"] += 1

    elif message.video:
        file_obj = message.video
        file_type = "video"
        session["video"] += 1

    elif message.document:
        file_obj = message.document
        file_type = "document"
        session["document"] += 1

    if not file_obj:
        return

    session["items"].append({
        "file_id": file_obj.file_id,
        "type": file_type,
        "size": getattr(file_obj, "file_size", 0) or 0
    })

    # DELETE biar clean
    try:
        await message.delete()
    except:
        pass

    # 🔥 RATE LIMIT EDIT
    now = time.time()
    if now - last_edit_time.get(user_id, 0) < 1.2:
        return

    last_edit_time[user_id] = now

    total = len(session["items"])
    size_mb = round(sum(x["size"] for x in session["items"]) / (1024 * 1024), 2)

    bar = "█" * min(total, 10) + "░" * (10 - min(total, 10))

    text = (
        "📤 <b>UPLOAD PROGRESS</b>\n\n"
        f"[{bar}] {total} file\n"
        f"🖼 {session['photo']} | 🎬 {session['video']} | 📁 {session['document']}\n"
        f"💾 {size_mb} MB"
    )

    try:
        await safe_send(
            message.bot.edit_message_text,
            chat_id=message.chat.id,
            message_id=session["msg_id"],
            text=text,
            parse_mode="HTML",
            reply_markup=upload_kb()
        )
    except:
        pass


# =========================
# DONE UPLOAD
# =========================

@router.callback_query(F.data == "upload_done")
async def done(call: CallbackQuery):

    user_id = call.from_user.id
    s = upload_sessions.get(user_id)

    if not s or not s.get("items"):
        return await call.answer("Upload kosong 😏", show_alert=True)

    # 🔥 HARD LOCK
    if s.get("processing"):
        return await call.answer("Sedang diproses...")

    s["processing"] = True
    s["locked"] = True
    s["step"] = "title"

    try:
        await call.message.edit_text(
            "💀 <b>MARKET SETUP</b>\n\nKirim JUDUL PRODUCT:",
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer()


# =========================
# FLOW ENGINE
# =========================

@router.message(F.text)
async def market_flow(message: Message):

    user_id = message.from_user.id
    s = upload_sessions.get(user_id)

    if not s or not s.get("locked"):
        return

    if user_states.get(user_id, {}).get("mode") != "upload":
        return

    text = message.text.strip()
    if not text or text.startswith("/"):
        return

    # TITLE
    if s["step"] == "title":

        if len(text) > 100:
            return await message.answer("Judul terlalu panjang.")

        s["title"] = text
        s["step"] = "paid"

        return await message.answer("💰 PAID? (YES/NO)")

    # PAID
    if s["step"] == "paid":

        if text.lower() not in ("yes", "no"):
            return await message.answer("Ketik YES atau NO.")

        s["paid"] = text.lower() == "yes"
        s["step"] = "price" if s["paid"] else "final"

        return await message.answer("💵 PRICE?" if s["paid"] else "📤 SHARE? (YES/NO)")

    # PRICE
    if s["step"] == "price":

        if not text.isdigit():
            return await message.answer("Masukkan angka.")

        price = int(text)

        if price < 100:
            return await message.answer("Minimal 100.")
        if price > 100_000_000:
            return await message.answer("Terlalu besar.")

        s["price"] = price
        s["step"] = "final"

        return await message.answer("📤 SHARE? (YES/NO)")

    # FINAL
    if s["step"] == "final":

        if text.lower() not in ("yes", "no"):
            return await message.answer("Ketik YES atau NO.")

        s["share"] = text.lower() == "yes"

        code = generate_file_code(
            s["video"],
            s["photo"],
            s["document"]
        )

        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():

                    await conn.execute("""
                        INSERT INTO codes(
                            code, owner_id, price, is_paid,
                            total_media, total_size, created_at
                        )
                        VALUES($1,$2,$3,$4,$5,$6,NOW())
                    """,
                        code,
                        user_id,
                        s.get("price", 0),
                        s.get("paid", False),
                        len(s["items"]),
                        sum(x["size"] for x in s["items"])
                    )

                    await conn.executemany("""
                        INSERT INTO medias(
                            code, file_id, file_type, file_size
                        )
                        VALUES($1,$2,$3,$4)
                    """,
                        [
                            (
                                code,
                                m["file_id"],
                                m["type"],
                                m["size"]
                            )
                            for m in s["items"]
                        ]
                    )

            await safe_send(
                message.answer,
                f"✅ SUCCESS\n\nCODE:\n<code>{code}</code>",
                parse_mode="HTML"
            )

            # SHARE
            if s["share"]:
                try:
                    await safe_send(
                        message.bot.send_message,
                        GROUP_ID,
                        (
                            "📦 FILE BARU\n\n"
                            f"📌 Judul : {s['title']}\n"
                            f"🔑 Code : {code}\n"
                            f"📁 Total : {len(s['items'])} File\n"
                            f"💰 Status : {'PAID' if s['paid'] else 'FREE'}"
                        )
                    )
                except Exception as e:
                    print("[SHARE ERROR]", e)

        except Exception as e:
            print("[UPLOAD SAVE ERROR]", e)
            await message.answer("❌ Gagal menyimpan.")

        # CLEAN SESSION
        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        last_edit_time.pop(user_id, None)


# =========================
# CANCEL
# =========================

@router.callback_query(F.data == "upload_cancel")
async def cancel(call: CallbackQuery):

    user_id = call.from_user.id

    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    try:
        await call.message.edit_text("❌ Upload dibatalkan.")
    except:
        pass

    await call.answer("Cancelled")

# =========================
# CONFIG
# =========================

COOLDOWN_TIME = 5
PAGE_DELAY = 1
SESSION_TTL = 3600

cooldown = {"global": {}}
pagination_lock = {}
page_history = {}
page_cooldown = {}

CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/xxxx")
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/xxxx")

# =========================
# NORMALIZER
# =========================

def normalize_type(t: str) -> str:
    t = (t or "").lower().strip()

    if t in ("photo", "image", "img", "jpg", "jpeg", "png"):
        return "photo"
    if t in ("video", "vid", "mp4", "mov"):
        return "video"

    return "document"

# =========================
# COOLDOWN
# =========================

def is_cooldown(user_id: int) -> bool:
    now = time.time()
    last = cooldown["global"].get(user_id, 0)

    if now - last < COOLDOWN_TIME:
        return True

    cooldown["global"][user_id] = now
    return False

# =========================
# SAFE STATE
# =========================

def get_state(user_id: int):
    state = user_states.get(user_id)

    if not state:
        return None

    if time.time() - state.get("created_at", 0) > SESSION_TTL:
        user_states.pop(user_id, None)
        return None

    return state

# =========================
# LOAD MEDIA
# =========================

async def load_media(code: str):
    if not code:
        return []

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT file_id, file_type, COALESCE(file_size,0) AS file_size
                FROM medias
                WHERE code=$1
                ORDER BY id ASC
                """,
                code
            )

        return [
            {
                "file_id": r["file_id"],
                "file_type": normalize_type(r["file_type"]),
                "file_size": int(r["file_size"] or 0)
            }
            for r in rows
        ]

    except Exception as e:
        print("LOAD MEDIA ERROR:", e)
        return []

# =========================
# SEND MEDIA
# =========================

async def send_media(bot, chat_id: int, chunk: list):
    if not chunk:
        return False

    media = []

    for item in chunk[:5]:
        file_id = item.get("file_id")
        file_type = item.get("file_type")  # sudah normalize

        if not file_id:
            continue

        if file_type == "photo":
            media.append(InputMediaPhoto(media=file_id))
        elif file_type == "video":
            media.append(InputMediaVideo(media=file_id))
        else:
            media.append(InputMediaDocument(media=file_id))

    if not media:
        return False

    try:
        await safe_send(bot.send_media_group, chat_id=chat_id, media=media)
        return True
    except Exception as e:
        print("SEND MEDIA ERROR:", e)
        return False

# =========================
# KEYBOARD
# =========================

def build_kb(user_id: int, page: int, total_pages: int):

    history = page_history.get(user_id, set())

    nav_row = [
        InlineKeyboardButton(
            text="⬅ Prev" if page > 0 else "⛔",
            callback_data="prev" if page > 0 else "noop"
        ),
        InlineKeyboardButton(
            text="➡ Next" if page < total_pages - 1 else "⛔",
            callback_data="next" if page < total_pages - 1 else "noop"
        )
    ]

    page_row = []

    start = max(0, page - 2)
    end = min(total_pages, start + 5)

    for i in range(start, end):
        mark = "🟢" if i == page else "🟡" if i in history else "⚪"

        page_row.append(
            InlineKeyboardButton(
                text=f"{i+1}{mark}",
                callback_data=f"page:{i}"
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            nav_row,
            page_row,
            [
                InlineKeyboardButton(text="📢 CHANNEL", url=CHANNEL_LINK),
                InlineKeyboardButton(text="💬 GROUP", url=GROUP_LINK)
            ]
        ]
    )

# =========================
# RENDER PAGE
# =========================

async def render_page(user_id: int, bot, chat_id: int):

    state = get_state(user_id)
    if not state:
        return

    data = state.get("data", [])
    if not data:
        return

    page = max(0, state.get("page", 0))
    size = state.get("page_size", 5)

    total_pages = max(1, (len(data) + size - 1) // size)

    start = page * size
    end = start + size

    chunk = data[start:end]

    page_history.setdefault(user_id, set()).add(page)

    ok = await send_media(bot, chat_id, chunk)
    if not ok:
        return

    text = (
        f"📦 CODE: <code>{state['code']}</code>\n"
        f"📄 Page: {page+1}/{total_pages}\n"
        f"📁 Item: {start+1}-{start+len(chunk)} / {len(data)}"
    )

    kb = build_kb(user_id, page, total_pages)

    old_msg = state.get("last_panel_msg")

    if old_msg:
        try:
            await bot.delete_message(chat_id, old_msg)
        except:
            pass

    msg = await bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=kb
    )

    state["last_panel_msg"] = msg.message_id

# =========================
# GET FILE START
# =========================

@router.message(F.text == "📥 Get File")
async def start_get(message: Message):

    user_states[message.from_user.id] = {
        "mode": "getfile",
        "created_at": time.time()
    }

    await message.answer("📥 Kirim CODE")

# =========================
# RECEIVE CODE
# =========================

@router.message(F.text & ~F.text.startswith("/"))
async def receive_code(message: Message):

    user_id = message.from_user.id
    state = get_state(user_id)

    if not state or state.get("mode") != "getfile":
        return

    if is_cooldown(user_id):
        return await message.answer("⏳ Jangan spam")

    text = (message.text or "").strip()

    codes = re.findall(r"decodefilebot_[A-Za-z0-9]+", text)

    if not codes:
        return await message.answer("❌ CODE tidak valid")

    code = codes[0]

    if not await is_paid(code):
        return await message.answer(
            "🔒 CODE berbayar",
            reply_markup=payment_button(code)
        )

    data = await load_media(code)

    if not data:
        return await message.answer("❌ File tidak ditemukan")

    user_states[user_id] = {
        "mode": "view",
        "code": code,
        "page": 0,
        "page_size": 5,
        "data": data,
        "last_panel_msg": None,
        "created_at": time.time()
    }

    page_history[user_id] = set()

    await message.answer(f"📦 FILE: {len(data)} item")

    await render_page(user_id, message.bot, message.chat.id)

# =========================
# PAGINATION
# =========================

@router.callback_query(F.data.in_(["next", "prev"]) | F.data.startswith("page:"))
async def pagination(call: CallbackQuery):

    user_id = call.from_user.id

    if pagination_lock.get(user_id):
        return await call.answer("⏳ Loading...")

    now = time.time()

    if now - page_cooldown.get(user_id, 0) < PAGE_DELAY:
        return await call.answer("⏳ Tunggu")

    pagination_lock[user_id] = True
    page_cooldown[user_id] = now

    try:
        state = get_state(user_id)

        if not state:
            return await call.answer("Session expired")

        data = state.get("data", [])
        if not data:
            return await call.answer("No data")

        page = state.get("page", 0)
        size = state.get("page_size", 5)

        max_page = (len(data) - 1) // size

        if call.data == "next":
            page += 1
        elif call.data == "prev":
            page -= 1
        else:
            page = int(call.data.split(":")[1])

        page = max(0, min(page, max_page))
        state["page"] = page

        await render_page(user_id, call.bot, call.message.chat.id)

        await call.answer()

    finally:
        pagination_lock.pop(user_id, None)

# =========================
# NOOP
# =========================

@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):
    await call.answer()

# =========================
# CLEANUP
# =========================

async def cleanup_sessions():
    while True:
        try:
            now = time.time()

            for uid, state in list(user_states.items()):
                if now - state.get("created_at", now) > SESSION_TTL:
                    user_states.pop(uid, None)
                    page_history.pop(uid, None)
                    pagination_lock.pop(uid, None)
                    page_cooldown.pop(uid, None)

        except Exception as e:
            print("CLEANUP ERROR:", e)

        await asyncio.sleep(300)
    
# =========================
# USER CACHE (SAFE)
# =========================

USER_COOLDOWN = 30
user_cache = {}
user_cache_lock = asyncio.Lock()

# =========================
# CLEANUP CACHE
# =========================

async def cleanup_user_cache():
    while True:
        try:
            now = time.time()

            for uid, ts in list(user_cache.items()):
                if now - ts > USER_COOLDOWN * 2:
                    user_cache.pop(uid, None)

        except Exception as e:
            print("USER CACHE CLEAN ERROR:", e)

        await asyncio.sleep(60)

# =========================
# ADD / UPDATE USER
# =========================

async def add_user(user_id: int, username=None, fullname=None) -> bool:

    username = (username or "").strip()
    fullname = (fullname or "").strip()

    now = time.time()

    # LOCK biar gak race
    async with user_cache_lock:

        last = user_cache.get(user_id, 0)

        if now - last < USER_COOLDOWN:
            return False

        user_cache[user_id] = now

    try:
        async with db_pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO users (user_id, username, fullname, created_at, last_seen)
                VALUES ($1,$2,$3,NOW(),NOW())

                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = CASE
                        WHEN EXCLUDED.username <> '' THEN EXCLUDED.username
                        ELSE users.username
                    END,
                    fullname = CASE
                        WHEN EXCLUDED.fullname <> '' THEN EXCLUDED.fullname
                        ELSE users.fullname
                    END,
                    last_seen = NOW()
                """,
                user_id,
                username,
                fullname
            )

        return True

    except Exception as e:
        print(f"[ADD USER ERROR] {e}")
        return False

# =========================
# ANTI DOUBLE ACCOUNT (IMPROVED)
# =========================

async def detect_double_account(user_id: int, username: str):

    if not username:
        return False

    try:
        async with db_pool.acquire() as conn:

            rows = await conn.fetch(
                """
                SELECT user_id FROM users
                WHERE username=$1
                ORDER BY created_at ASC
                LIMIT 2
                """,
                username
            )

        # kalau lebih dari 1 dan bukan user ini
        return any(r["user_id"] != user_id for r in rows)

    except Exception as e:
        print("DOUBLE CHECK ERROR:", e)
        return False

# =========================
# WALLET FETCH (SAFE)
# =========================

async def get_wallet(conn, user_id: int):

    row = await conn.fetchrow(
        "SELECT * FROM wallets WHERE user_id=$1",
        user_id
    )

    if not row:
        return {
            "balance": 0,
            "total_in": 0,
            "total_out": 0
        }

    return row

# =========================
# USER ACTIVITY CHART (FIXED)
# =========================

async def get_user_chart(conn, user_id: int):

    rows = await conn.fetch(
        """
        SELECT DATE(created_at) as d, COUNT(*) as total
        FROM codes
        WHERE owner_id=$1
        GROUP BY d
        ORDER BY d DESC
        LIMIT 7
        """,
        user_id
    )

    if not rows:
        return "📉 No activity"

    rows = list(reversed(rows))  # biar urut dari lama ke baru

    chart = "📊 Activity (7 Days)\n"

    for r in rows:
        bar = "█" * min(r["total"], 10)
        chart += f"{r['d']} : {bar} ({r['total']})\n"

    return chart

# =========================
# NOTIFY WALLET (ANTI SPAM)
# =========================

notify_cache = {}

async def notify_wallet_change(bot, user_id: int, amount: int):

    now = time.time()
    last = notify_cache.get(user_id, 0)

    # minimal jeda 5 detik
    if now - last < 5:
        return

    notify_cache[user_id] = now

    try:
        await bot.send_message(
            user_id,
            f"🔔 <b>TRANSACTION UPDATE</b>\n\n💰 +Rp {amount:,}",
            parse_mode="HTML"
        )
    except Exception as e:
        print("NOTIFY ERROR:", e)

# =========================
# ACCOUNT DASHBOARD (FIXED)
# =========================

@router.message(F.text.in_(["/account", "📊 Account"]))
async def account_cmd(message: Message):

    user = message.from_user

    if not user:
        return

    user_id = user.id
    username = user.username or ""
    fullname = user.full_name or "No Name"

    # =========================
    # SAVE USER (SAFE)
    # =========================
    try:
        await add_user(user_id, username, fullname)
    except Exception as e:
        print("ADD USER FAIL:", e)

    # =========================
    # ANTI DOUBLE ACCOUNT
    # =========================
    try:
        if username and await detect_double_account(user_id, username):
            return await message.answer(
                "🚫 <b>Duplicate Account Detected</b>\n\n"
                "Gunakan 1 akun saja.",
                parse_mode="HTML"
            )
    except Exception as e:
        print("DOUBLE CHECK FAIL:", e)

    # =========================
    # FETCH DATA
    # =========================
    try:
        async with db_pool.acquire() as conn:

            # INIT WALLET
            await conn.execute("""
                INSERT INTO wallets (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
            """, user_id)

            wallet = await get_wallet(conn, user_id)

            codes = await conn.fetch("""
                SELECT code, total_media, total_size, status
                FROM codes
                WHERE owner_id=$1
                ORDER BY id DESC
                LIMIT 5
            """, user_id)

            total_codes = await conn.fetchval("""
                SELECT COUNT(*) FROM codes WHERE owner_id=$1
            """, user_id) or 0

            chart = await get_user_chart(conn, user_id)

    except Exception as e:
        print("DB ERROR:", e)
        return await message.answer("❌ Database error, coba lagi nanti.")

    # =========================
    # SAFE WALLET PARSE
    # =========================
    w = wallet or {}

    saldo = int(w.get("saldo", w.get("balance", 0) or 0))
    pending = int(w.get("total_pending", 0))
    process = int(w.get("total_process", 0))
    failed = int(w.get("total_failed", 0))
    success = int(w.get("total_success", 0))

    bank_name = w.get("bank_name") or "-"
    bank_number = w.get("bank_number") or "-"
    bank_owner = w.get("bank_owner") or "-"

    ewallet_type = w.get("ewallet_type") or "-"
    ewallet_number = w.get("ewallet_number") or "-"

    global_type = w.get("global_type") or "-"
    global_account = w.get("global_account") or "-"

    username_text = f"@{username}" if username else "Tidak ada"

    # =========================
    # RECENT CODES FORMAT (SAFE)
    # =========================
    if codes:
        code_lines = []

        for c in codes:
            size_mb = (c["total_size"] or 0) / 1048576

            code_lines.append(
                f"📦 <code>{c['code']}</code>\n"
                f"📁 {c['total_media']} file | 💾 {size_mb:.2f} MB\n"
                f"⚡ {c['status']}"
            )

        code_text = "\n\n".join(code_lines)

    else:
        code_text = "❌ Belum ada code"

    # =========================
    # TEXT (OPTIMIZED)
    # =========================
    text = (
        "━━━━━━━━━━━━━━\n"
        "👤 <b>ACCOUNT</b>\n"
        "━━━━━━━━━━━━━━\n\n"

        f"🆔 <code>{user_id}</code>\n"
        f"👤 {fullname}\n"
        f"🔗 {username_text}\n\n"

        "💰 <b>WALLET</b>\n"
        f"💵 {saldo:,}\n"
        f"🟡 {pending:,} | 🔵 {process:,}\n"
        f"🔴 {failed:,} | 🟢 {success:,}\n\n"

        "📊 <b>STATS</b>\n"
        f"📦 Total Code: {total_codes}\n"
        f"{chart}\n\n"

        "🏦 <b>BANK</b>\n"
        f"{bank_name} | {bank_number}\n\n"

        "📱 <b>EWALLET</b>\n"
        f"{ewallet_type} | {ewallet_number}\n\n"

        "🌍 <b>GLOBAL</b>\n"
        f"{global_type} | {global_account}\n\n"

        "📦 <b>RECENT</b>\n"
        f"{code_text}"
    )

    # =========================
    # SEND
    # =========================
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=saldo_kb()
    )

# =========================
# IMPORT
# =========================
import time
from datetime import datetime

from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

# =========================
# CONFIG
# =========================
MIN_WITHDRAW = 10000
MAX_WITHDRAW = 500000

USER_COOLDOWN = 2
user_cache = {}

ADMIN_IDS = {6847035364}

# =========================
# HELPER
# =========================
def is_admin(user_id: int):
    return user_id in ADMIN_IDS


def is_cooldown(user_id: int):
    now = time.time()
    last = user_cache.get(user_id, 0)

    if now - last < USER_COOLDOWN:
        return True

    user_cache[user_id] = now
    return False


def is_withdraw_open():
    now = datetime.now()
    return 8 <= now.hour < 20


# =========================
# WALLET INIT
# =========================
async def ensure_wallet(conn, user_id):
    await conn.execute(
        """
        INSERT INTO wallets (user_id)
        VALUES ($1)
        ON CONFLICT (user_id) DO NOTHING
        """,
        user_id
    )


# =========================
# KEYBOARD (FINAL)
# =========================
def saldo_kb():
    wd_open = is_withdraw_open()

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Deposit",
                    callback_data="deposit"
                ),
                InlineKeyboardButton(
                    text="💸 Withdraw" if wd_open else "🔒 Withdraw",
                    callback_data="withdraw"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Refresh",
                    callback_data="refresh_account"
                ),
                InlineKeyboardButton(
                    text="📜 History",
                    callback_data="wallet_history"
                )
            ]
        ]
    )


# =========================
# /SALDO COMMAND
# =========================
@router.message(F.text.in_(["/saldo", "💰 Wallet"]))
async def saldo_cmd(message: Message):

    user_id = message.from_user.id

    if is_cooldown(user_id):
        return await message.answer("⏳ Tunggu sebentar...")

    try:
        async with db_pool.acquire() as conn:

            await ensure_wallet(conn, user_id)

            row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(saldo,0) AS saldo,
                    COALESCE(total_pending,0) AS pending,
                    COALESCE(total_process,0) AS process,
                    COALESCE(total_failed,0) AS failed,
                    COALESCE(total_success,0) AS success
                FROM wallets
                WHERE user_id=$1
                """,
                user_id
            )

        saldo = row["saldo"] if row else 0
        pending = row["pending"] if row else 0
        process = row["process"] if row else 0
        failed = row["failed"] if row else 0
        success = row["success"] if row else 0

        total = saldo + pending + process + failed + success

        wd_open = is_withdraw_open()
        status = "🟢 OPEN" if wd_open else "🔴 CLOSED"

        text = (
            "━━━━━━━━━━━━━━\n"
            "💰 <b>WALLET</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💵 Saldo : Rp {saldo:,}\n\n"

            f"🟡 Pending : Rp {pending:,}\n"
            f"🔄 Process : Rp {process:,}\n"
            f"❌ Failed  : Rp {failed:,}\n"
            f"✅ Success : Rp {success:,}\n\n"

            f"📊 Total : Rp {total:,}\n\n"

            f"⏰ Withdraw : {status}\n"
            "🕗 08:00 - 20:00 WIB\n\n"

            f"💸 Min : Rp {MIN_WITHDRAW:,}\n"
            f"💸 Max : Rp {MAX_WITHDRAW:,}\n"
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=saldo_kb()
        )

    except Exception as e:
        print("SALDO ERROR:", e)
        await message.answer("❌ Gagal memuat saldo")


# =========================
# REFRESH BUTTON (CLEAN)
# =========================
@router.callback_query(F.data == "refresh_account")
async def refresh_account(call: CallbackQuery):

    user_id = call.from_user.id

    if is_cooldown(user_id):
        return await call.answer("⏳ Slow...", show_alert=True)

    await call.answer("🔄 Refresh...")

    try:
        async with db_pool.acquire() as conn:

            await ensure_wallet(conn, user_id)

            row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(saldo,0) AS saldo,
                    COALESCE(total_pending,0) AS pending,
                    COALESCE(total_process,0) AS process,
                    COALESCE(total_failed,0) AS failed,
                    COALESCE(total_success,0) AS success
                FROM wallets
                WHERE user_id=$1
                """,
                user_id
            )

        saldo = row["saldo"]
        pending = row["pending"]
        process = row["process"]
        failed = row["failed"]
        success = row["success"]

        total = saldo + pending + process + failed + success

        wd_open = is_withdraw_open()
        status = "🟢 OPEN" if wd_open else "🔴 CLOSED"

        text = (
            "🔄 <b>UPDATED</b>\n\n"
            f"💵 {saldo:,}\n"
            f"📊 Total : {total:,}\n"
            f"⏰ {status}"
        )

        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=saldo_kb()
        )

    except Exception as e:
        print("REFRESH ERROR:", e)
        await call.answer("❌ Error", show_alert=True)


# =========================
# WITHDRAW LOCK
# =========================
@router.callback_query(F.data == "withdraw")
async def withdraw_handler(call: CallbackQuery):

    if not is_withdraw_open():
        return await call.answer(
            "🚫 Withdraw tutup\nJam 08:00 - 20:00",
            show_alert=True
        )

    await call.answer("💸 Masuk menu withdraw...")

# =========================
# ADD BALANCE (SAFE)
# =========================
async def add_balance(conn, user_id: int, amount: int):

    if amount <= 0:
        return False

    await conn.execute(
        """
        UPDATE wallets
        SET saldo = saldo + $2,
            total_success = total_success + $2
        WHERE user_id = $1
        """,
        user_id, amount
    )

    return True


# =========================
# WITHDRAW RESULT ENUM
# =========================
class WD:
    SUCCESS = "SUCCESS"
    NO_WALLET = "NO_WALLET"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    NOT_ENOUGH = "NOT_ENOUGH"
    NO_BANK = "NO_BANK"
    ERROR = "ERROR"


# =========================
# CREATE WITHDRAW (FULL SAFE)
# =========================
async def create_withdraw(conn, user_id: int, amount: int):

    if amount < MIN_WITHDRAW:
        return WD.INVALID_AMOUNT

    try:
        async with conn.transaction():

            # LOCK ROW (ANTI RACE CONDITION)
            wallet = await conn.fetchrow(
                """
                SELECT saldo, bank_name, bank_number, bank_owner
                FROM wallets
                WHERE user_id=$1
                FOR UPDATE
                """,
                user_id
            )

            if not wallet:
                return WD.NO_WALLET

            # VALIDASI BANK
            if not all([
                wallet["bank_name"],
                wallet["bank_number"],
                wallet["bank_owner"]
            ]):
                return WD.NO_BANK

            saldo = wallet["saldo"]

            if saldo < amount:
                return WD.NOT_ENOUGH

            # UPDATE WALLET (ATOMIC)
            await conn.execute(
                """
                UPDATE wallets
                SET saldo = saldo - $2,
                    total_pending = total_pending + $2
                WHERE user_id=$1
                """,
                user_id, amount
            )

            # INSERT REQUEST
            await conn.execute(
                """
                INSERT INTO withdraw_requests(
                    user_id,
                    amount,
                    bank_name,
                    bank_number,
                    bank_owner,
                    status
                )
                VALUES($1,$2,$3,$4,$5,'PENDING')
                """,
                user_id,
                amount,
                wallet["bank_name"],
                wallet["bank_number"],
                wallet["bank_owner"]
            )

        return WD.SUCCESS

    except Exception as e:
        print("WITHDRAW ERROR:", e)
        return WD.ERROR
# =========================
# FRAUD CHECK (REAL)
# =========================
async def fraud_check(conn, user_id, amount):

    rows = await conn.fetchval("""
        SELECT COUNT(*)
        FROM withdraw_requests
        WHERE user_id=$1
        AND created_at > NOW() - INTERVAL '1 hour'
    """, user_id)

    if rows >= 3:
        return False

    return True


# =========================
# WITHDRAW LIST (UPGRADE UI)
# =========================
@router.callback_query(F.data.startswith("wd_page:"))
async def withdraw_page(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("NO ACCESS")

    page = int(call.data.split(":")[1])
    limit = 5
    offset = page * limit

    async with db_pool.acquire() as conn:

        rows = await conn.fetch("""
            SELECT *
            FROM withdraw_requests
            WHERE status='PENDING'
            ORDER BY id ASC
            LIMIT $1 OFFSET $2
        """, limit, offset)

    if not rows:
        return await call.message.edit_text("📭 No request")

    text = "🏧 <b>WITHDRAW LIST</b>\n\n"
    kb = []

    for r in rows:
        text += (
            f"🆔 {r['id']} | 👤 {r['user_id']}\n"
            f"💸 Rp {r['amount']:,}\n"
            f"🏦 {r['bank_name']}\n\n"
        )

        kb.append([
            InlineKeyboardButton(
                text=f"✅ {r['id']}",
                callback_data=f"wd_ok:{r['id']}"
            ),
            InlineKeyboardButton(
                text=f"❌ {r['id']}",
                callback_data=f"wd_no:{r['id']}"
            )
        ])

    kb.append([
        InlineKeyboardButton("⬅ Prev", callback_data=f"wd_page:{max(page-1,0)}"),
        InlineKeyboardButton("➡ Next", callback_data=f"wd_page:{page+1}")
    ])

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


# =========================
# APPROVE WITHDRAW (ATOMIC)
# =========================
@router.callback_query(F.data.startswith("wd_ok:"))
async def approve_withdraw(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("NO ACCESS")

    req_id = int(call.data.split(":")[1])

    async with db_pool.acquire() as conn:
        async with conn.transaction():

            req = await conn.fetchrow("""
                SELECT *
                FROM withdraw_requests
                WHERE id=$1
                FOR UPDATE
            """, req_id)

            if not req:
                return await call.answer("Not found")

            if req["status"] != "PENDING":
                return await call.answer("Already processed")

            # FRAUD CHECK
            ok = await fraud_check(conn, req["user_id"], req["amount"])
            if not ok:
                return await call.answer("FRAUD DETECTED", show_alert=True)

            # UPDATE REQUEST
            await conn.execute("""
                UPDATE withdraw_requests
                SET status='APPROVED'
                WHERE id=$1
            """, req_id)

            # UPDATE WALLET
            await conn.execute("""
                UPDATE wallets
                SET total_pending = total_pending - $2,
                    total_success = total_success + $2
                WHERE user_id=$1
            """, req["user_id"], req["amount"])

    # NOTIFY USER
    try:
        await call.message.bot.send_message(
            req["user_id"],
            f"✅ WITHDRAW APPROVED\n💸 Rp {req['amount']:,}"
        )
    except:
        pass

    # GROUP LOG
    await call.message.bot.send_message(
        GROUP_ID,
        f"🟢 APPROVED\nUser: {req['user_id']}\nRp {req['amount']:,}"
    )

    log_action(call.from_user.id, "APPROVE_WITHDRAW", req["user_id"])

    await call.message.edit_text(f"✅ APPROVED ID {req_id}")


# =========================
# REJECT WITHDRAW (ATOMIC)
# =========================
@router.callback_query(F.data.startswith("wd_no:"))
async def reject_withdraw(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("NO ACCESS")

    req_id = int(call.data.split(":")[1])

    async with db_pool.acquire() as conn:
        async with conn.transaction():

            req = await conn.fetchrow("""
                SELECT *
                FROM withdraw_requests
                WHERE id=$1
                FOR UPDATE
            """, req_id)

            if not req:
                return await call.answer("Not found")

            if req["status"] != "PENDING":
                return await call.answer("Already processed")

            # BALIKIN SALDO
            await conn.execute("""
                UPDATE wallets
                SET saldo = saldo + $2,
                    total_pending = total_pending - $2
                WHERE user_id=$1
            """, req["user_id"], req["amount"])

            # UPDATE STATUS
            await conn.execute("""
                UPDATE withdraw_requests
                SET status='REJECTED'
                WHERE id=$1
            """, req_id)

    # NOTIFY USER
    try:
        await call.message.bot.send_message(
            req["user_id"],
            f"❌ WITHDRAW REJECTED\n💸 Rp {req['amount']:,}"
        )
    except:
        pass

    # GROUP LOG
    await call.message.bot.send_message(
        GROUP_ID,
        f"🔴 REJECTED\nUser: {req['user_id']}\nRp {req['amount']:,}"
    )

    log_action(call.from_user.id, "REJECT_WITHDRAW", req["user_id"])

    await call.message.edit_text(f"❌ REJECTED ID {req_id}")


from datetime import datetime
import time

# =========================
# ADMIN STATISTIC
# =========================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("NO ACCESS")

    today = datetime.utcnow().date()

    async with db_pool.acquire() as conn:

        today_withdraw = await conn.fetchval("""
            SELECT COALESCE(SUM(amount),0)
            FROM withdraw_requests
            WHERE status='APPROVED'
            AND DATE(created_at) = $1
        """, today)

        total_users = await conn.fetchval("""
            SELECT COUNT(*) FROM users
        """)

    text = (
        "📊 ADMIN STATISTICS\n\n"
        f"👥 Users: {total_users}\n"
        f"💸 Withdraw Today: Rp {today_withdraw:,}\n"
    )

    await call.message.edit_text(text)


# =========================
# VIP CONFIG
# =========================
VIP_PRICE = 50000
VIP_DURATION_DAYS = 30

VIP_ORDER_LOCK = set()

# FORMAT:
# user_id: expired_timestamp
PAID_VIP_USERS = {}

ADMIN_ID = 6847035364


# =========================
# CHECK VIP ACTIVE
# =========================
def is_vip(user_id: int):
    now = time.time()

    if user_id in PAID_VIP_USERS:
        if PAID_VIP_USERS[user_id] > now:
            return True
        else:
            # expired
            PAID_VIP_USERS.pop(user_id)

    return False


# =========================
# VIP KEYBOARD
# =========================
def vip_kb(user_id: int):

    pay_code = f"vip_{user_id}_{int(time.time())}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("💎 BUY VIP NOW", callback_data=f"vip_buy:{pay_code}")],
            [InlineKeyboardButton("💬 CHAT ADMIN VIP", url="https://t.me/penngewe")],
            [InlineKeyboardButton("❌ Cancel", callback_data="vip_cancel")]
        ]
    )


# =========================
# /VIP COMMAND
# =========================
@router.message(F.text == "/vip")
async def vip_cmd(message: Message):

    user_id = message.from_user.id

    if is_vip(user_id):
        return await message.answer("✅ Kamu sudah VIP aktif")

    text = (
        "💎 <b>VIP ACCESS</b>\n\n"
        "⚡ Unlimited Upload File\n"
        "⚡ Priority Processing\n"
        "⚡ Fast Get File\n\n"
        f"💰 Rp {VIP_PRICE:,} / {VIP_DURATION_DAYS} hari"
    )

    await message.answer(
        text,
        reply_markup=vip_kb(user_id),
        parse_mode="HTML"
    )


# =========================
# BUY VIP
# =========================
@router.callback_query(F.data.startswith("vip_buy:"))
async def vip_buy(call: CallbackQuery):

    user_id = call.from_user.id
    pay_code = call.data.split(":")[1]

    if user_id in VIP_ORDER_LOCK:
        return await call.answer("⏳ Tunggu proses sebelumnya")

    VIP_ORDER_LOCK.add(user_id)

    try:
        if is_vip(user_id):
            return await call.answer("✅ Kamu sudah VIP")

        pay_url = f"https://your-payment-link.com/pay?vip_code={pay_code}"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton("💳 BAYAR VIP", url=pay_url)],
                [InlineKeyboardButton("📩 CHECK STATUS", callback_data=f"vip_check:{pay_code}")]
            ]
        )

        await call.message.edit_text(
            f"💳 <b>VIP PAYMENT</b>\n\n"
            f"💰 Rp {VIP_PRICE:,}\n"
            "Status: PENDING",
            reply_markup=kb,
            parse_mode="HTML"
        )

    finally:
        VIP_ORDER_LOCK.discard(user_id)

    await call.answer()


# =========================
# CHECK PAYMENT
# =========================
@router.callback_query(F.data.startswith("vip_check:"))
async def vip_check(call: CallbackQuery):

    user_id = call.from_user.id

    # 🔥 GANTI INI KE PAYMENT API / WEBHOOK
    paid = False  

    if paid:
        expired = time.time() + (VIP_DURATION_DAYS * 86400)
        PAID_VIP_USERS[user_id] = expired

        await call.message.edit_text(
            "✅ <b>VIP AKTIF</b>\n\n🎉 Selamat!",
            parse_mode="HTML"
        )

        await call.bot.send_message(
            ADMIN_ID,
            f"💎 VIP PAID\nUser: {user_id}"
        )

    else:
        await call.answer("⏳ Belum dibayar", show_alert=True)


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "vip_cancel")
async def vip_cancel(call: CallbackQuery):

    await call.message.edit_text(
        "❌ <b>VIP CLOSED</b>",
        parse_mode="HTML"
    )

    await call.answer()
import time

# =========================
# ADMIN CONFIG (PRO MAX)
# =========================
SUPERADMINS = {6847035364}
ADMINS = set(SUPERADMINS)

ADMIN_LOG = []
CMD_LOCK = {}

MAX_LOG = 1000


# =========================
# ADMIN CHECK
# =========================
def is_admin(user_id: int):
    return user_id in ADMINS


def is_superadmin(user_id: int):
    return user_id in SUPERADMINS


# =========================
# LOG SYSTEM (ANTI OVERFLOW)
# =========================
def log_admin(action, actor, target=None):
    ADMIN_LOG.append({
        "action": action,
        "actor": actor,
        "target": target,
        "time": time.time()
    })

    if len(ADMIN_LOG) > MAX_LOG:
        ADMIN_LOG.pop(0)


# =========================
# RATE LIMIT ADMIN CMD
# =========================
def admin_cooldown(user_id: int):
    now = time.time()
    last = CMD_LOCK.get(user_id, 0)

    if now - last < 2:
        return True

    CMD_LOCK[user_id] = now
    return False


# =========================
# ADD ADMIN (SUPER SAFE)
# =========================
@router.message(F.text.startswith("/addadmin"))
async def add_admin(message: Message):

    uid = message.from_user.id

    # 🔥 HARUS SUPERADMIN
    if not is_superadmin(uid):
        return await message.answer("🚫 ONLY SUPERADMIN")

    if admin_cooldown(uid):
        return await message.answer("⏳ Slow down")

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("❌ Format:\n/addadmin <user_id>")

    try:
        new_id = int(parts[1])
    except:
        return await message.answer("❌ Invalid ID")

    if new_id in ADMINS:
        return await message.answer("⚠️ Already admin")

    # 🔥 ANTI SELF ADD LOOP
    if new_id == uid:
        return await message.answer("⚠️ Already you")

    ADMINS.add(new_id)
    log_admin("ADD_ADMIN", uid, new_id)

    await message.answer(f"✅ ADMIN ADDED\nID: {new_id}")


# =========================
# REMOVE ADMIN (LOCKED)
# =========================
@router.message(F.text.startswith("/deladmin"))
async def del_admin(message: Message):

    uid = message.from_user.id

    if not is_superadmin(uid):
        return await message.answer("🚫 ONLY SUPERADMIN")

    parts = message.text.split()
    if len(parts) != 2:
        return await message.answer("❌ Format:\n/deladmin <user_id>")

    try:
        target = int(parts[1])
    except:
        return await message.answer("❌ Invalid ID")

    if target in SUPERADMINS:
        return await message.answer("🛑 Cannot remove superadmin")

    if target not in ADMINS:
        return await message.answer("❌ Not admin")

    ADMINS.remove(target)
    log_admin("REMOVE_ADMIN", uid, target)

    await message.answer(f"❌ ADMIN REMOVED\nID: {target}")


# =========================
# STATISTICS MAX (SAFE)
# =========================
@router.message(F.text == "/stat")
async def stat_cmd(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 ACCESS DENIED")

    if admin_cooldown(message.from_user.id):
        return await message.answer("⏳ Slow down")

    try:
        async with db_pool.acquire() as conn:

            users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            codes = await conn.fetchval("SELECT COUNT(*) FROM codes") or 0
            media = await conn.fetchval("SELECT COUNT(*) FROM medias") or 0

            total_size = await conn.fetchval(
                "SELECT COALESCE(SUM(total_size),0) FROM codes"
            ) or 0

            withdraw_total = await conn.fetchval(
                "SELECT COALESCE(SUM(amount),0) FROM withdraw_requests WHERE status='APPROVED'"
            ) or 0

            pending = await conn.fetchval(
                "SELECT COUNT(*) FROM withdraw_requests WHERE status='PENDING'"
            ) or 0

    except Exception as e:
        print("STAT ERROR:", e)
        return await message.answer("⚠️ DB ERROR")

    mb = total_size / (1024 * 1024)

    await message.answer(
        "📊 <b>ADMIN DASHBOARD MAX</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 Users        : {users}\n"
        f"🔑 Codes        : {codes}\n"
        f"📦 Media        : {media}\n"
        f"💾 Storage      : {mb:.2f} MB\n\n"
        f"💸 Total WD     : Rp {withdraw_total:,}\n"
        f"⏳ Pending WD   : {pending}\n"
        "━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )
import asyncio
import time
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

# =========================
# BROADCAST PRO MAX
# =========================
@router.message(F.text.startswith("/broadcast"))
async def broadcast_cmd(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 ACCESS DENIED")

    text = message.text.replace("/broadcast", "").strip()
    if not text:
        return await message.answer("❌ Format:\n/broadcast pesan")

    try:
        async with db_pool.acquire() as conn:
            users = await conn.fetch("SELECT user_id FROM users")
    except:
        return await message.answer("⚠️ DB ERROR")

    total = len(users)
    sent = 0
    failed = 0

    status = await message.answer(
        f"📡 <b>BROADCAST START</b>\n\n"
        f"👥 Users: {total}\n"
        f"⏳ Progress: 0%",
        parse_mode="HTML"
    )

    start = time.time()

    # 🔥 LIMIT CONCURRENT TASK
    semaphore = asyncio.Semaphore(20)

    async def send(uid):
        nonlocal sent, failed

        async with semaphore:
            try:
                await message.bot.send_message(uid, text)
                sent += 1

            except TelegramForbiddenError:
                # user block bot
                failed += 1

            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                return await send(uid)

            except:
                failed += 1

    tasks = []
    update_every = 50  # update UI tiap 50 user

    for i, u in enumerate(users, start=1):
        tasks.append(send(u["user_id"]))

        # 🔥 jalanin batch async
        if len(tasks) >= 50:
            await asyncio.gather(*tasks)
            tasks = []

        # 🔥 update progress
        if i % update_every == 0:
            percent = (i / total) * 100

            try:
                await status.edit_text(
                    f"📡 <b>BROADCAST RUNNING</b>\n\n"
                    f"👥 Total   : {total}\n"
                    f"📤 Sent    : {sent}\n"
                    f"❌ Failed  : {failed}\n"
                    f"⏳ Progress: {percent:.1f}%",
                    parse_mode="HTML"
                )
            except:
                pass

    # sisa task
    if tasks:
        await asyncio.gather(*tasks)

    duration = time.time() - start

    await status.edit_text(
        "📡 <b>BROADCAST DONE</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        f"👥 Total  : {total}\n"
        f"📤 Sent   : {sent}\n"
        f"❌ Failed : {failed}\n"
        f"⏱ Time   : {duration:.1f}s\n"
        "━━━━━━━━━━━━━━",
        parse_mode="HTML"
    )

# =========================
# HELP DATA (ANTI RIBET)
# =========================
HELP_TEXT = {
    "upload": (
        "📤 <b>UPLOAD FILE</b>\n\n"
        "1. Klik <b>Up File</b>\n"
        "2. Kirim media\n"
        "3. Klik <b>DONE</b>\n"
        "4. Dapat <b>CODE</b>"
    ),
    "get": (
        "📥 <b>GET FILE</b>\n\n"
        "1. Klik <b>Get File</b>\n"
        "2. Kirim <b>CODE</b>\n"
        "3. File otomatis dikirim"
    ),
    "account": (
        "👤 <b>ACCOUNT</b>\n\n"
        "• ID User\n"
        "• Username\n"
        "• Statistik File"
    ),
    "vip": (
        "💎 <b>VIP SYSTEM</b>\n\n"
        "⚡ Unlimited Upload\n"
        "⚡ Fast Access\n"
        "⚡ Priority System\n\n"
        "Gunakan /vip untuk upgrade"
    ),
}


# =========================
# KEYBOARD
# =========================
def help_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Upload", callback_data="help:upload"),
                InlineKeyboardButton(text="📥 Get File", callback_data="help:get"),
            ],
            [
                InlineKeyboardButton(text="👤 Account", callback_data="help:account"),
                InlineKeyboardButton(text="💎 VIP", callback_data="help:vip"),
            ],
            [
                InlineKeyboardButton(text="🛠 Admin", callback_data="help:admin"),
            ],
            [
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:start"),
            ],
        ]
    )


# =========================
# HELP ENTRY (DIGABUNG)
# =========================
@router.message(F.text.in_({"/help", "❓ Help"}))
async def help_entry(message: Message):
    await message.answer(
        "🔥 <b>HELP CENTER</b>\n\nPilih menu di bawah 👇",
        parse_mode="HTML",
        reply_markup=help_kb(),
    )


# =========================
# HELP ROUTER (CLEAN)
# =========================
@router.callback_query(F.data.startswith("help:"))
async def help_router(call: CallbackQuery):

    menu = call.data.split(":")[1]

    # 🔥 ADMIN CHECK
    if menu == "admin":
        if not is_admin(call.from_user.id):
            return await call.answer("🚫 No Access", show_alert=True)

        text = (
            "🛠 <b>ADMIN PANEL</b>\n\n"
            "/stat → statistik\n"
            "/broadcast → kirim pesan\n"
            "/addadmin → tambah admin\n"
            "/deladmin → hapus admin"
        )

    else:
        text = HELP_TEXT.get(menu, "❌ Menu tidak ditemukan")

    try:
        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=help_kb()
        )
    except:
        pass

    await call.answer()


# =========================
# BACK TO MENU
# =========================
@router.callback_query(F.data == "menu:start")
async def back_to_start(call: CallbackQuery):

    try:
        await call.message.edit_text(
            "🔥 <b>MAIN MENU</b>\n\nPilih menu di bawah 👇",
            parse_mode="HTML",
            reply_markup=help_kb()
        )
    except:
        pass

    await call.answer()

import signal

# =========================
# SAFE TASK WRAPPER
# =========================
async def safe_task(coro, name="task"):
    while True:
        try:
            await coro
        except asyncio.CancelledError:
            print(f"🛑 {name} stopped")
            break
        except Exception as e:
            print(f"❌ {name} error:", e)
            await asyncio.sleep(3)


# =========================
# MAIN (FIXED PRODUCTION)
# =========================
async def main():
    global bot, dp  # 🔥 WAJIB kalau dipakai di file lain

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN tidak ditemukan")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL tidak ditemukan")

    print("🚨 FILE KELOAD")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    shutdown_event = asyncio.Event()

    # =========================
    # SIGNAL HANDLER
    # =========================
    def stop_signal(*args):
        print("⚠️ SIGNAL STOP RECEIVED")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_signal)
        except NotImplementedError:
            # 🔥 fix Railway / Windows
            pass

    # =========================
    # CLEAN WEBHOOK
    # =========================
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    print(f"🤖 LOGIN: @{me.username}")

    # =========================
    # INIT DB
    # =========================
    await init_db()
    print("🗄 DATABASE READY")

    # =========================
    # BACKGROUND TASK
    # =========================
    tasks = set()

    cleanup_task_runner = asyncio.create_task(
        safe_task(cleanup_sessions(), "cleanup_sessions")
    )
    tasks.add(cleanup_task_runner)

    print("⚙️ BACKGROUND TASK STARTED")

    # =========================
    # FASTAPI SERVER
    # =========================
    port = int(os.getenv("PORT", 8000))

    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

    server = uvicorn.Server(config)

    print("🚀 BOT STARTING...")

    # =========================
    # RUN TASKS (FIXED)
    # =========================
    polling_task = asyncio.create_task(dp.start_polling(bot))
    api_task = asyncio.create_task(server.serve())
    shutdown_task = asyncio.create_task(shutdown_event.wait())  # 🔥 FIX

    done, pending = await asyncio.wait(
        [polling_task, api_task, shutdown_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    print("⚠️ STOPPING SYSTEM...")

    # =========================
    # CANCEL TASK
    # =========================
    for task in pending:
        task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    # =========================
    # STOP BACKGROUND TASK
    # =========================
    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    # =========================
    # CLOSE DB
    # =========================
    try:
        if db_pool:
            await db_pool.close()
            print("🗄 DB CLOSED")
    except Exception as e:
        print("DB CLOSE ERROR:", e)

    # =========================
    # CLOSE BOT
    # =========================
    try:
        await bot.session.close()
        print("🤖 BOT CLOSED")
    except Exception as e:
        print("BOT CLOSE ERROR:", e)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 MANUAL STOP")
