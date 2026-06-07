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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(router)

# =========================
# LOAD ENV
# =========================

load_dotenv()

# =========================
# CORE CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CHANNEL_DB = os.getenv("CHANNEL_DB", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN tidak ditemukan")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL tidak ditemukan")

# =========================
# PAYMENT CONFIG
# =========================

PAYGG_SECRET = os.getenv("PAYGG_SECRET", "").strip()
PAYGG_API_KEY = os.getenv("PAYGG_API_KEY", "").strip()

# =========================
# OPTIONAL CONFIG
# =========================

UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "").strip()
VIP_LINK = os.getenv("VIP_LINK", "").strip()

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
            command_timeout=30,
            statement_cache_size=0,
        )

        async with db_pool.acquire() as conn:

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                fullname TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)

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

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS medias(
                id SERIAL PRIMARY KEY,
                code TEXT NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size BIGINT DEFAULT 0
            )
            """)

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions(
                id SERIAL PRIMARY KEY,
                order_id TEXT UNIQUE NOT NULL,
                user_id BIGINT NOT NULL,
                code TEXT,
                amount BIGINT DEFAULT 0,
                fee BIGINT DEFAULT 0,
                net BIGINT DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
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
);

        print("✅ Database Ready")

    except Exception as e:
        print(f"❌ Database Error: {e}")
        raise

# =========================
# CACHE / MEMORY
# =========================

cooldown = {
    "global": {},
    "page": {},
}

page_history = {}
page_cooldown = {}

user_click_lock = {}
upload_sessions = {}
user_states = {}

last_edit_time = {}
user_last_action = {}

force_cache = {}

broadcast_running = False
payment_cache = {}

user_upload_lock = {}
user_download_lock = {}

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


def user_limit(user_id: int) -> bool:
    now = time.time()

    last = user_last_action.get(user_id, 0)

    if now - last < USER_DELAY:
        return False

    user_last_action[user_id] = now
    return True


async def global_throttle():
    global last_global_send

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
# ROUTER
# =========================

router = Router()

# =========================
# KEYBOARD
# =========================

def get_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📤 Up File"),
                KeyboardButton(text="📥 Get File")
            ],
            [
                KeyboardButton(text="💰 Wallet"),
                KeyboardButton(text="🧾 Invoice")
            ],
            [
                KeyboardButton(text="📊 Account"),
                KeyboardButton(text="💸 Withdraw")
            ],
            [
                KeyboardButton(text="🔔 Status"),
                KeyboardButton(text="⭐ VIP")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Upload / ambil file / cek wallet... 💸"
    )
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

    async with httpx.AsyncClient(timeout=15) as client:

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

    return {
        "order_id": order_id,
        "qr_url": data.get("qr_url"),
        "expires_at": expires_at
    }


# =========================
# SEND QR
# =========================

async def send_qr(
    user_id: int,
    qr_url: str,
    caption: str
) -> int:

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
                    SELECT
                        order_id,
                        user_id,
                        message_id
                    FROM payments
                    WHERE status='pending'
                    AND expires_at < NOW()
                """)

                for row in rows:

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

    signature = request.headers.get(
        "X-Signature",
        ""
    )

    if not verify_signature(
        raw_body,
        signature
    ):
        return {
            "ok": False,
            "error": "invalid_signature"
        }

    order_id = data.get("order_id")
    status = data.get("status")
    amount = int(data.get("amount") or 0)

    if not order_id:
        return {"ok": False}

    if status not in (
        "paid",
        "failed",
        "expired"
    ):
        return {"ok": True}

    user_id = None
    code = None
    msg_id = None
    qr_message_id = None

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            payment = await conn.fetchrow("""
                SELECT
                    order_id,
                    user_id,
                    code,
                    status,
                    group_message_id,
                    message_id
                FROM payments
                WHERE order_id=$1
                FOR UPDATE
            """, order_id)

            if not payment:
                return {"ok": False}

            if payment["status"] == "paid":
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
                """,
                    amount,
                    user_id
                )

    # =========================
    # CHANNEL UPDATE
    # =========================

    if msg_id and NOTIFICATION_CHANNEL:

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
                text=(
                    f"{icon}\n\n"
                    f"User : {user_id}\n"
                    f"Code : {code}"
                )
            )

        except Exception as e:
            print("[CHANNEL UPDATE]", e)

    # =========================
    # USER ACTION
    # =========================

    try:

        if status == "paid":

            if qr_message_id:
                try:
                    await bot.delete_message(
                        user_id,
                        qr_message_id
                    )
                except Exception:
                    pass

            medias = await db_pool.fetch("""
                SELECT
                    file_id,
                    file_type
                FROM medias
                WHERE code=$1
            """, code)

            for media in medias:

                if media["file_type"] == "photo":

                    await safe_send(
                        bot.send_photo,
                        user_id,
                        media["file_id"]
                    )

                elif media["file_type"] == "video":

                    await safe_send(
                        bot.send_video,
                        user_id,
                        media["file_id"]
                    )

                else:

                    await safe_send(
                        bot.send_document,
                        user_id,
                        media["file_id"]
                    )

            await safe_send(
                bot.send_message,
                user_id,
                f"🟢 Pembayaran berhasil\n\nCode: {code}"
            )

        elif status == "expired":

            if qr_message_id:
                try:
                    await bot.delete_message(
                        user_id,
                        qr_message_id
                    )
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

    # FORCE SUB
    if FORCE_CHANNEL:

        joined = await check_force_sub(
            bot,
            user.id,
            FORCE_CHANNEL
        )

        if not joined:
            return await safe_send(
                message.answer,
                (
                    "🚫 AKSES DITOLAK\n\n"
                    "😏 Kamu belum join channel.\n"
                    "Tanpa itu, bot ini gak bisa dipakai.\n\n"
                    "👉 Join dulu lalu tekan tombol verifikasi."
                ),
                reply_markup=force_kb()
            )

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

    joined = await check_force_sub(
        bot,
        user_id,
        FORCE_CHANNEL
    )

    if not joined:
        return await call.answer(
            "🚫 Kamu belum join channel.",
            show_alert=True
        )

    try:
        await call.message.edit_text(
            "✅ VERIFIED\n\n😈 Akses berhasil dibuka."
        )
    except TelegramBadRequest:
        pass
    except Exception as e:
        print("[CHECK SUB ERROR]", e)

    await safe_send(
        call.message.answer,
        (
            "🔥 AKSES DIBUKA\n\n"
            "😈 Verifikasi berhasil.\n"
            "Silakan gunakan bot."
        ),
        reply_markup=get_keyboard()
    )

    await call.answer(
        "✅ Verified"
    )


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
# START UPLOAD
# =========================

@router.message(F.text == "📤 Up File")
async def up_file(message: Message):

    user_id = message.from_user.id

    if not user_limit(user_id):
        return await safe_send(
            message.answer,
            "⏳ Jangan spam ya 😏"
        )

    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    user_states[user_id] = {
        "mode": "upload"
    }

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

    if not session or not session.get("msg_id"):
        return

    # SESSION EXPIRE 30 MENIT
    if time.time() - session["created_at"] > 1800:

        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)

        return await message.answer(
            "⏰ Session upload expired.\nSilakan upload ulang."
        )

    # LIMIT FILE
    if len(session["items"]) >= 100:
        return await message.answer(
            "🚫 Maksimal 100 file per upload."
        )

    file_obj = None
    file_type = None

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

    try:
        await message.delete()
    except:
        pass

    now = time.time()

    if now - last_edit_time.get(user_id, 0) < 1.3:
        return

    last_edit_time[user_id] = now

    total = len(session["items"])

    size_mb = round(
        sum(x["size"] for x in session["items"]) / (1024 * 1024),
        2
    )

    bar = (
        "█" * min(total, 10)
        + "░" * (10 - min(total, 10))
    )

    text = (
        "📤 <b>UPLOAD PROGRESS</b>\n\n"
        f"[{bar}] {total} file\n"
        f"🖼 {session['photo']} | "
        f"🎬 {session['video']} | "
        f"📁 {session['document']}\n"
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
# GENERATE FILE CODE
# =========================

def generate_file_code(
    video_count: int,
    photo_count: int,
    document_count: int
) -> str:

    seed = (
        f"{video_count}"
        f"{photo_count}"
        f"{document_count}"
        f"{time.time()}"
        f"{secrets.token_hex(8)}"
    )

    return (
        "decodefilebot_" +
        hashlib.sha1(seed.encode()).hexdigest()[:16]
    )


# =========================
# DONE UPLOAD
# =========================

@router.callback_query(F.data == "upload_done")
async def done(call: CallbackQuery):

    user_id = call.from_user.id

    s = upload_sessions.get(user_id)

    if (
        not s
        or not isinstance(s, dict)
        or not s.get("items")
    ):
        return await call.answer(
            "Upload kosong 😏",
            show_alert=True
        )

    # ANTI DOUBLE CLICK
    if s.get("processing"):
        return await call.answer(
            "Sedang diproses..."
        )

    s["processing"] = True
    s["locked"] = True
    s["step"] = "title"

    await call.message.edit_text(
        "💀 MARKET SETUP\n\n"
        "Kirim JUDUL PRODUCT:"
    )

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

    if text.startswith("/"):
        return

    # TITLE
    if s["step"] == "title":

        s["title"] = text
        s["step"] = "paid"

        return await message.answer(
            "💰 PAID? (YES/NO)"
        )

    # PAID
    if s["step"] == "paid":

        s["paid"] = text.lower() == "yes"

        s["step"] = (
            "price"
            if s["paid"]
            else "final"
        )

        if s["paid"]:
            return await message.answer(
                "💵 PRICE?"
            )

        return await message.answer(
            "📤 SHARE? (YES/NO)"
        )

    # PRICE
    if s["step"] == "price":

        if not text.isdigit():
            return await message.answer(
                "Masukkan angka yang valid."
            )

        price = int(text)

        if price < 100:
            return await message.answer(
                "Minimal harga 100."
            )

        if price > 100000000:
            return await message.answer(
                "Harga terlalu besar."
            )

        s["price"] = price
        s["step"] = "final"

        return await message.answer(
            "📤 SHARE? (YES/NO)"
        )

    # FINAL
    if s["step"] == "final":

        s["share"] = text.lower() == "yes"

        code = generate_file_code(
            s["video"],
            s["photo"],
            s["document"]
        )

        try:

            async with db_pool.acquire() as conn:

                await conn.execute(
                    """
                    INSERT INTO codes(
                        code,
                        owner_id,
                        price,
                        is_paid,
                        total_media,
                        total_size,
                        created_at
                    )
                    VALUES(
                        $1,$2,$3,$4,$5,$6,NOW()
                    )
                    """,
                    code,
                    user_id,
                    s.get("price", 0),
                    s.get("paid", False),
                    len(s["items"]),
                    sum(
                        x["size"]
                        for x in s["items"]
                    )
                )

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

            await message.answer(
                f"✅ SUCCESS\n\nCODE:\n{code}"
            )

            # AUTO SHARE GROUP
            if s["share"]:

                try:
                    await message.bot.send_message(
                        GROUP_ID,
                        (
                            "📦 FILE BARU\n\n"
                            f"📌 Judul : {s['title']}\n"
                            f"🔑 Code : {code}\n"
                            f"📁 Total : {len(s['items'])} File\n"
                            f"💰 Status : "
                            f"{'PAID' if s['paid'] else 'FREE'}"
                        )
                    )

                except Exception as e:
                    print(
                        "[SHARE ERROR]",
                        e
                    )

        except Exception as e:

            print(
                "[UPLOAD SAVE ERROR]",
                e
            )

            await message.answer(
                "❌ Gagal menyimpan data."
            )

        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        last_edit_time.pop(user_id, None)


# =========================
# CANCEL
# =========================

@router.callback_query(F.data == "upload_cancel")
async def cancel(call: CallbackQuery):

    upload_sessions.pop(
        call.from_user.id,
        None
    )

    user_states.pop(
        call.from_user.id,
        None
    )

    last_edit_time.pop(
        call.from_user.id,
        None
    )

    await call.message.edit_text(
        "❌ Upload dibatalkan."
    )

    await call.answer()

# =========================
# CONFIG
# =========================

COOLDOWN_TIME = 5
PAGE_DELAY = 1

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
# PAID CHECK
# =========================

async def is_paid(code: str) -> bool:

    try:
        async with db_pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT is_paid
                FROM codes
                WHERE code=$1
                """,
                code
            )

            return bool(row and row["is_paid"])

    except Exception as e:
        print("PAID CHECK ERROR:", e)
        return False


BAYARGG_URL = os.getenv(
    "BAYARGG_URL",
    "https://your-bayargg-link.com/pay?code="
)


def payment_button(code: str):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 BAYAR SEKARANG",
                    url=f"{BAYARGG_URL}{code}"
                )
            ]
        ]
    )


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
                SELECT
                    file_id,
                    file_type,
                    COALESCE(file_size,0) AS file_size
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
        file_type = normalize_type(item.get("file_type"))

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

        await safe_send(
            bot.send_media_group,
            chat_id=chat_id,
            media=media
        )

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
            text="⬅ Prev" if page > 0 else "⛔ Prev",
            callback_data="prev" if page > 0 else "noop"
        ),
        InlineKeyboardButton(
            text="➡ Next" if page < total_pages - 1 else "⛔ Next",
            callback_data="next" if page < total_pages - 1 else "noop"
        )
    ]

    page_row = []

    start = max(0, page - 2)
    end = min(total_pages, start + 5)

    for i in range(start, end):

        mark = (
            "🟢" if i == page
            else "🟡" if i in history
            else "⚪"
        )

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
                InlineKeyboardButton(
                    text="📢 CHANNEL",
                    url=CHANNEL_LINK
                ),
                InlineKeyboardButton(
                    text="💬 GROUP",
                    url=GROUP_LINK
                )
            ]
        ]
    )


# =========================
# RENDER PAGE
# =========================

async def render_page(
    user_id: int,
    bot,
    chat_id: int
):

    state = user_states.get(user_id)

    if not state:
        return

    data = state.get("data", [])

    if not data:
        return

    page = max(0, state.get("page", 0))
    size = state.get("page_size", 5)

    total_pages = max(
        1,
        (len(data) + size - 1) // size
    )

    start = page * size
    end = start + size

    chunk = data[start:end]

    page_history.setdefault(
        user_id,
        set()
    ).add(page)

    ok = await send_media(
        bot,
        chat_id,
        chunk
    )

    if not ok:
        return

    text = (
        f"📦 CODE: <code>{state['code']}</code>\n"
        f"📄 Page: {page+1}/{total_pages}\n"
        f"📁 Item: {start+1}-{start+len(chunk)} / {len(data)}"
    )

    kb = build_kb(
        user_id,
        page,
        total_pages
    )

    old_msg = state.get("last_panel_msg")

    if old_msg:
        try:
            await bot.delete_message(
                chat_id,
                old_msg
            )
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
# START GET FILE
# =========================

@router.message(F.text == "📥 Get File")
async def start_get(message: Message):

    user_states[message.from_user.id] = {
        "mode": "getfile",
        "created_at": time.time()
    }

    await message.answer(
        "📥 Kirim CODE"
    )


# =========================
# RECEIVE CODE
# =========================

@router.message(F.text & ~F.text.startswith("/"))
async def receive_code(message: Message):

    user_id = message.from_user.id

    state = user_states.get(user_id)

    if not state:
        return

    if state.get("mode") != "getfile":
        return

    if is_cooldown(user_id):
        return await message.answer(
            "⏳ Jangan spam"
        )

    text = (message.text or "").strip()

    codes = re.findall(
        r"decodefilebot_[A-Za-z0-9]+",
        text
    )

    if not codes:
        return await message.answer(
            "❌ CODE tidak valid"
        )

    code = codes[0]

    if not await is_paid(code):

        return await message.answer(
            "🔒 CODE ini berbayar",
            reply_markup=payment_button(code)
        )

    data = await load_media(code)

    if not data:
        return await message.answer(
            "❌ File tidak ditemukan"
        )

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

    await message.answer(
        f"📦 FILE DITEMUKAN: {len(data)}"
    )

    await render_page(
        user_id,
        message.bot,
        message.chat.id
    )


# =========================
# PAGINATION
# =========================

@router.callback_query(
    F.data.in_(["next", "prev"])
    | F.data.startswith("page:")
)
async def pagination(call: CallbackQuery):

    user_id = call.from_user.id

    now = time.time()

    if now - page_cooldown.get(user_id, 0) < PAGE_DELAY:
        return await call.answer(
            "⏳ Tunggu sebentar"
        )

    page_cooldown[user_id] = now

    if pagination_lock.get(user_id):
        return await call.answer(
            "⏳ Loading..."
        )

    pagination_lock[user_id] = True

    try:

        state = user_states.get(user_id)

        if not state:
            return await call.answer(
                "Session expired"
            )

        data = state.get("data", [])

        if not data:
            return await call.answer(
                "No data"
            )

        page = state.get("page", 0)
        size = state.get("page_size", 5)

        max_page = (
            len(data) - 1
        ) // size

        if call.data == "next":
            page += 1

        elif call.data == "prev":
            page -= 1

        else:
            page = int(
                call.data.split(":")[1]
            )

        page = max(
            0,
            min(page, max_page)
        )

        state["page"] = page

        await render_page(
            user_id,
            call.bot,
            call.message.chat.id
        )

        await call.answer()

    finally:

        pagination_lock.pop(
            user_id,
            None
        )


# =========================
# NOOP
# =========================

@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery):

    await call.answer()


# =========================
# SESSION CLEANER
# =========================

async def cleanup_sessions():

    while True:

        try:

            now = time.time()

            for uid, state in list(user_states.items()):

                created = state.get(
                    "created_at",
                    now
                )

                if now - created > 3600:

                    user_states.pop(uid, None)
                    page_history.pop(uid, None)
                    pagination_lock.pop(uid, None)
                    page_cooldown.pop(uid, None)

        except Exception as e:
            print("CLEANUP ERROR:", e)

        await asyncio.sleep(300)
    
# =========================
# USER CACHE
# =========================

USER_COOLDOWN = 30  # detik
user_cache = {}

# =========================
# ADD / UPDATE USER (PRO)
# =========================

async def add_user(
    user_id: int,
    username: str | None = None,
    fullname: str | None = None
) -> bool:

    username = (username or "").strip()
    fullname = (fullname or "").strip()

    now = int(time.time())

    # =========================
    # ANTI SPAM CACHE
    # =========================
    last = user_cache.get(user_id, 0)

    if now - last < USER_COOLDOWN:
        return False

    user_cache[user_id] = now

    try:

        async with db_pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    username,
                    fullname,
                    created_at,
                    last_seen
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    NOW(),
                    NOW()
                )

                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = CASE
                        WHEN EXCLUDED.username <> ''
                        THEN EXCLUDED.username
                        ELSE users.username
                    END,

                    fullname = CASE
                        WHEN EXCLUDED.fullname <> ''
                        THEN EXCLUDED.fullname
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
# ACCOUNT DASHBOARD (FULL UPGRADED SYSTEM)
# =========================

import time
from datetime import datetime
import asyncio

# =========================
# ANTI DOUBLE ACCOUNT (BASIC SAFE CHECK)
# =========================
user_device_map = {}  # optional fingerprint simple


async def detect_double_account(user_id: int, username: str):
    """
    simple anti double account logic
    """
    if not username:
        return False

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT user_id FROM users
            WHERE username=$1
            ORDER BY created_at ASC
            LIMIT 1
        """, username)

    if row and row["user_id"] != user_id:
        return True

    return False


# =========================
# REALTIME WALLET FETCH
# =========================
async def get_wallet(conn, user_id: int):
    return await conn.fetchrow("""
        SELECT * FROM wallets WHERE user_id=$1
    """, user_id)


# =========================
# SIMPLE GRAPH (LAST 7 DAYS CODES)
# =========================
async def get_user_chart(conn, user_id: int):
    rows = await conn.fetch("""
        SELECT DATE(created_at) as d, COUNT(*) as total
        FROM codes
        WHERE owner_id=$1
        GROUP BY d
        ORDER BY d DESC
        LIMIT 7
    """, user_id)

    if not rows:
        return "📉 No data"

    chart = "📊 Activity (7 Days)\n"
    for r in rows:
        bar = "█" * min(r["total"], 10)
        chart += f"{r['d']} : {bar} ({r['total']})\n"

    return chart


# =========================
# NOTIFICATION SYSTEM (OPTIONAL HOOK)
# =========================
async def notify_wallet_change(bot, user_id: int, amount: int):
    try:
        await bot.send_message(
            user_id,
            f"🔔 <b>TRANSACTION UPDATE</b>\n\n💰 +Rp {amount:,}",
            parse_mode="HTML"
        )
    except:
        pass


# =========================
# ACCOUNT DASHBOARD
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

    # =========================
    # ANTI DOUBLE ACCOUNT CHECK
    # =========================
    if await detect_double_account(user.id, user.username or ""):
        return await message.answer(
            "🚫 <b>Duplicate Account Detected</b>\n\n"
            "Sistem mendeteksi akun ganda.",
            parse_mode="HTML"
        )

    async with db_pool.acquire() as conn:

        # INIT WALLET
        await conn.execute("""
            INSERT INTO wallets (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id)

        wallet = await get_wallet(conn, user.id)

        codes = await conn.fetch("""
            SELECT code, total_media, total_size, status
            FROM codes
            WHERE owner_id=$1
            ORDER BY id DESC
            LIMIT 5
        """, user.id)

        total_codes = await conn.fetchval("""
            SELECT COUNT(*) FROM codes WHERE owner_id=$1
        """, user.id) or 0

        chart = await get_user_chart(conn, user.id)

    # =========================
    # SAFE WALLET PARSE
    # =========================
    w = wallet or {}

    saldo = w.get("saldo", 0)
    pending = w.get("total_pending", 0)
    process = w.get("total_process", 0)
    failed = w.get("total_failed", 0)
    success = w.get("total_success", 0)

    bank_name = w.get("bank_name") or "-"
    bank_number = w.get("bank_number") or "-"
    bank_owner = w.get("bank_owner") or "-"

    ewallet_type = w.get("ewallet_type") or "-"
    ewallet_number = w.get("ewallet_number") or "-"

    global_type = w.get("global_type") or "-"
    global_account = w.get("global_account") or "-"

    username = f"@{user.username}" if user.username else "Tidak ada"

    # =========================
    # RECENT CODES FORMAT
    # =========================
    if codes:
        code_text = "\n\n".join(
            f"📦 <code>{c['code']}</code>\n"
            f"📁 File: {c['total_media']} | 💾 {(c['total_size'] or 0)/1048576:.2f} MB\n"
            f"⚡ Status: {c['status']}"
            for c in codes
        )
    else:
        code_text = "❌ Belum ada code"

    # =========================
    # MAIN TEXT
    # =========================
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>ACCOUNT DASHBOARD PRO</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🆔 ID       : <code>{user.id}</code>\n"
        f"👤 Name     : {user.full_name}\n"
        f"🔗 Username : {username}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "💰 REALTIME WALLET\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"💵 Saldo   : Rp {saldo:,}\n"
        f"🟡 Pending : Rp {pending:,}\n"
        f"🔵 Process : Rp {process:,}\n"
        f"🔴 Failed  : Rp {failed:,}\n"
        f"🟢 Success : Rp {success:,}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📊 STATISTIK REALTIME\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{chart}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🏦 BANK\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{bank_name} | {bank_number} | {bank_owner}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📱 EWALLET\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{ewallet_type} | {ewallet_number}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🌍 GLOBAL\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{global_type} | {global_account}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📦 RECENT CODES\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{code_text}\n"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=saldo_kb())


# =========================
# WALLET KEYBOARD (UPGRADE)
# =========================

def saldo_kb():

    now = datetime.now()
    wd_open = 8 <= now.hour < 20

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💳 Deposit",
                    callback_data="deposit"
                ),
                InlineKeyboardButton(
                    text="🏧 Withdraw",
                    callback_data="withdraw" if wd_open else "closed"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Refresh",
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
# REFRESH ACCOUNT (REALTIME BUTTON)
# =========================

@router.callback_query(F.data == "refresh_account")
async def refresh_account(call: CallbackQuery):

    await call.answer("🔄 Refreshing...")

    # re-call command
    fake_msg = call.message
    fake_msg.from_user = call.from_user

    await account_cmd(fake_msg)
# =========================
# IMPORT
# =========================
import time
from datetime import datetime
from aiogram import F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================
# CONFIG
# =========================
GROUP_ID = -1003920865154
MIN_WITHDRAW = 50000

USER_COOLDOWN = 2
user_cache = {}

AUDIT_LOG = []
PROCESSED_TX = set()
ACTIVE_LOCK = {}

ADMIN_IDS = {6847035364}

# =========================
# ADMIN CHECK
# =========================
def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# LOG SYSTEM
# =========================
def log_action(actor_id, action, target_id=None):
    AUDIT_LOG.append({
        "actor": actor_id,
        "action": action,
        "target": target_id,
        "time": time.time()
    })

# =========================
# WALLET INIT
# =========================
async def ensure_wallet(conn, user_id):
    await conn.execute(
        """
        INSERT INTO wallets (
            user_id,
            saldo,
            total_pending,
            total_process,
            total_failed,
            total_success,
            bank_name,
            bank_number,
            bank_owner
        )
        VALUES ($1,0,0,0,0,0,'','','')
        ON CONFLICT (user_id) DO NOTHING
        """,
        user_id
    )


# =========================
# SALDO BUTTON
# =========================
def saldo_kb():
    now = datetime.now()
    wd_open = 8 <= now.hour < 20

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💸 Withdraw" if wd_open else "🔒 Withdraw",
                    callback_data="withdraw"
                ),
                InlineKeyboardButton(
                    text="💳 Deposit",
                    callback_data="deposit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Riwayat",
                    callback_data="wallet_history"
                )
            ]
        ]
    )


# =========================
# /SALDO (UPGRADED DASHBOARD)
# =========================
@router.message(F.text == "/saldo")
async def saldo_cmd(message: Message):

    user_id = message.from_user.id

    try:
        async with db_pool.acquire() as conn:

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

        now_hour = datetime.now().hour
        wd_open = 8 <= now_hour < 20
        status = "🟢 OPEN" if wd_open else "🔴 CLOSED"

        text = (
            "━━━━━━━━━━━━━━\n"
            "💰 <b>WALLET DASHBOARD</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💵 Saldo : Rp {saldo:,}\n\n"

            "━━━━━━━━━━━━━━\n"
            f"🟡 Pending : Rp {pending:,}\n"
            f"🔄 Process : Rp {process:,}\n"
            f"❌ Failed  : Rp {failed:,}\n"
            f"✅ Success : Rp {success:,}\n\n"

            "━━━━━━━━━━━━━━\n"
            f"📊 Total : Rp {total:,}\n\n"

            "━━━━━━━━━━━━━━\n"
            f"⏰ Withdraw : {status}\n"
            "🕗 08:00 - 20:00 WIB\n\n"

            "━━━━━━━━━━━━━━\n"
            "💸 Min Withdraw : Rp 10.000\n"
            "💸 Max Withdraw : Rp 500.000\n"
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
# ADD BALANCE (DEPOSIT SYSTEM)
# =========================
async def add_balance(conn, user_id, amount):

    await conn.execute(
        """
        UPDATE wallets
        SET saldo = saldo + $2,
            total_success = total_success + $2
        WHERE user_id=$1
        """,
        user_id, amount
    )


# =========================
# CREATE WITHDRAW (SAFE LOCK)
# =========================
async def create_withdraw(conn, user_id, amount):

    if ACTIVE_LOCK.get(user_id):
        return "LOCKED"

    wallet = await conn.fetchrow(
        "SELECT saldo, bank_name, bank_number, bank_owner FROM wallets WHERE user_id=$1",
        user_id
    )

    if not wallet:
        return False

    if amount < MIN_WITHDRAW:
        return False

    if wallet["saldo"] < amount:
        return False

    ACTIVE_LOCK[user_id] = True

    await conn.execute(
        """
        UPDATE wallets
        SET saldo = saldo - $2,
            total_pending = total_pending + $2
        WHERE user_id=$1
        """,
        user_id, amount
    )

    await conn.execute(
        """
        INSERT INTO withdraw_requests(
            user_id, amount,
            bank_name, bank_number, bank_owner,
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

    return True
# =========================
# ADMIN CONFIG
# =========================
GROUP_ID = -1003920865154
ADMIN_IDS = {6847035364}

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# MEMORY STORAGE
# =========================
PROCESSED_TX = set()
ACTIVE_LOCK = {}
AUDIT_LOG = []


# =========================
# LOG ACTION
# =========================
def log_action(actor_id, action, target_id=None, extra=None):
    AUDIT_LOG.append({
        "actor": actor_id,
        "action": action,
        "target": target_id,
        "extra": extra,
        "time": time.time()
    })


# =========================
# FRAUD DETECTOR (SIMPLE)
# =========================
async def fraud_check(conn, user_id, amount):
    """
    RULE:
    - max 3 withdraw per 1 hour
    - max 500k per request (already enforced elsewhere)
    """

    rows = await conn.fetch("""
        SELECT created_at
        FROM withdraw_requests
        WHERE user_id=$1
        ORDER BY id DESC
        LIMIT 5
    """, user_id)

    if len(rows) >= 3:
        return False

    return True


# =========================
# ADMIN PANEL
# =========================
@router.message(F.text == "/admin")
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 NO ACCESS")

    await message.answer(
        "🛠 ADMIN PANEL",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton("📥 Withdraw List", callback_data="wd_page:0"),
                InlineKeyboardButton("📊 Statistik", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton("📜 Audit Log", callback_data="audit")
            ]
        ])
    )


# =========================
# WITHDRAW LIST (PAGINATION)
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
            SELECT * FROM withdraw_requests
            WHERE status='PENDING'
            ORDER BY id ASC
            LIMIT $1 OFFSET $2
        """, limit, offset)

        total = await conn.fetchval("""
            SELECT COUNT(*) FROM withdraw_requests WHERE status='PENDING'
        """)

    if not rows:
        return await call.message.edit_text("📭 No request")

    text = "🏧 WITHDRAW LIST\n\n"

    for r in rows:
        text += (
            f"ID: {r['id']}\n"
            f"User: {r['user_id']}\n"
            f"Amount: Rp {r['amount']:,}\n"
            f"Bank: {r['bank_name']}\n\n"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("⬅ Prev", callback_data=f"wd_page:{max(page-1,0)}"),
            InlineKeyboardButton("➡ Next", callback_data=f"wd_page:{page+1}")
        ]
    ])

    await call.message.edit_text(text, reply_markup=kb)


# =========================
# APPROVE WITHDRAW
# =========================
@router.callback_query(F.data.startswith("wd_ok:"))
async def approve_withdraw(call: CallbackQuery):

    req_id = int(call.data.split(":")[1])

    async with db_pool.acquire() as conn:

        req = await conn.fetchrow(
            "SELECT * FROM withdraw_requests WHERE id=$1",
            req_id
        )

        if not req:
            return await call.answer("Not found")

        if req["status"] != "PENDING":
            return await call.answer("Already processed")

        if req_id in PROCESSED_TX:
            return await call.answer("Duplicate")

        # FRAUD CHECK
        ok = await fraud_check(conn, req["user_id"], req["amount"])
        if not ok:
            return await call.answer("FRAUD DETECTED")

        PROCESSED_TX.add(req_id)
        ACTIVE_LOCK.pop(req["user_id"], None)

        await conn.execute("""
            UPDATE withdraw_requests
            SET status='APPROVED'
            WHERE id=$1
        """, req_id)

        await conn.execute("""
            UPDATE wallets
            SET total_pending = total_pending - $2,
                total_success = total_success + $2
            WHERE user_id=$1
        """, req["user_id"], req["amount"])

    # =========================
    # NOTIFY USER (REALTIME)
    # =========================
    try:
        await call.message.bot.send_message(
            req["user_id"],
            f"✅ WITHDRAW APPROVED\n\n💸 Rp {req['amount']:,}"
        )
    except:
        pass

    # =========================
    # GROUP LOG
    # =========================
    await call.message.bot.send_message(
        GROUP_ID,
        f"🟢 APPROVED WITHDRAW\nUser: {req['user_id']}\nAmount: Rp {req['amount']:,}"
    )

    log_action(call.from_user.id, "APPROVE_WITHDRAW", req["user_id"])

    await call.message.edit_text(f"✅ APPROVED ID {req_id}")


# =========================
# REJECT WITHDRAW
# =========================
@router.callback_query(F.data.startswith("wd_no:"))
async def reject_withdraw(call: CallbackQuery):

    req_id = int(call.data.split(":")[1])

    async with db_pool.acquire() as conn:

        req = await conn.fetchrow(
            "SELECT * FROM withdraw_requests WHERE id=$1",
            req_id
        )

        if not req:
            return await call.answer("Not found")

        if req["status"] != "PENDING":
            return await call.answer("Already processed")

        if req_id in PROCESSED_TX:
            return await call.answer("Duplicate")

        PROCESSED_TX.add(req_id)
        ACTIVE_LOCK.pop(req["user_id"], None)

        await conn.execute("""
            UPDATE wallets
            SET saldo = saldo + $2,
                total_pending = total_pending - $2
            WHERE user_id=$1
        """, req["user_id"], req["amount"])

        await conn.execute("""
            UPDATE withdraw_requests
            SET status='REJECTED'
            WHERE id=$1
        """, req_id)

    # =========================
    # NOTIFY USER (REALTIME)
    # =========================
    try:
        await call.message.bot.send_message(
            req["user_id"],
            f"❌ WITHDRAW REJECTED\n\n💸 Rp {req['amount']:,}"
        )
    except:
        pass

    # =========================
    # GROUP LOG
    # =========================
    await call.message.bot.send_message(
        GROUP_ID,
        f"🔴 REJECTED WITHDRAW\nUser: {req['user_id']}\nAmount: Rp {req['amount']:,}"
    )

    log_action(call.from_user.id, "REJECT_WITHDRAW", req["user_id"])

    await call.message.edit_text(f"❌ REJECTED ID {req_id}")


# =========================
# ADMIN STATISTIC
# =========================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return await call.answer("NO ACCESS")

    async with db_pool.acquire() as conn:

        today_withdraw = await conn.fetchval("""
            SELECT COALESCE(SUM(amount),0)
            FROM withdraw_requests
            WHERE status='APPROVED'
        """)

        total_users = await conn.fetchval("""
            SELECT COUNT(*) FROM users
        """)

    text = (
        "📊 ADMIN STATISTICS\n\n"
        f"👥 Users: {total_users}\n"
        f"💸 Total Withdraw: Rp {today_withdraw:,}\n"
    )

    await call.message.edit_text(text)
        
# =========================
# VIP CONFIG
# =========================
VIP_PRICE = 50000
VIP_DURATION_DAYS = 30

VIP_ORDER_LOCK = set()
PAID_VIP_USERS = set()  # kalau pakai DB, ganti ini

ADMIN_ID = 6847035364


# =========================
# VIP KEYBOARD (START BUY)
# =========================
def vip_kb(user_id: int):

    pay_code = f"vip_{user_id}_{int(time.time())}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💎 BUY VIP NOW",
                    callback_data=f"vip_buy:{pay_code}"
                )
            ],
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
# /VIP COMMAND
# =========================
@router.message(F.text == "/vip")
async def vip_cmd(message: Message):

    user_id = message.from_user.id

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
        "💰 <b>PRICE</b>\n"
        f"Rp {VIP_PRICE:,} / {VIP_DURATION_DAYS} days\n\n"
        "━━━━━━━━━━━━━━\n"
        "💀 <b>NOTICE</b>\n"
        "━━━━━━━━━━━━━━\n"
        "• VIP aktif otomatis setelah pembayaran\n"
        "• Tidak refund\n"
        "• Sistem anti abuse aktif\n"
    )

    await message.answer(
        text,
        reply_markup=vip_kb(user_id),
        parse_mode="HTML"
    )


# =========================
# BUY VIP CLICK
# =========================
@router.callback_query(F.data.startswith("vip_buy:"))
async def vip_buy(call: CallbackQuery):

    user_id = call.from_user.id
    pay_code = call.data.split(":")[1]

    # =========================
    # ANTI DOUBLE ORDER
    # =========================
    if user_id in VIP_ORDER_LOCK:
        return await call.answer("⏳ Order masih diproses")

    VIP_ORDER_LOCK.add(user_id)

    try:
        # =========================
        # CHECK ALREADY VIP
        # =========================
        if user_id in PAID_VIP_USERS:
            return await call.answer("✅ Kamu sudah VIP")

        # =========================
        # PAYMENT LINK (BAYARGG / QRIS)
        # =========================
        pay_url = f"https://your-payment-link.com/pay?vip_code={pay_code}"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💳 BAYAR VIP",
                        url=pay_url
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📩 CHECK STATUS",
                        callback_data=f"vip_check:{pay_code}"
                    )
                ]
            ]
        )

        await call.message.edit_text(
            "💳 <b>VIP PAYMENT</b>\n\n"
            f"💰 Amount: Rp {VIP_PRICE:,}\n"
            "⏳ Status: PENDING\n\n"
            "Klik tombol di bawah untuk bayar:",
            reply_markup=kb,
            parse_mode="HTML"
        )

    finally:
        VIP_ORDER_LOCK.discard(user_id)

    await call.answer()


# =========================
# CHECK PAYMENT STATUS
# =========================
@router.callback_query(F.data.startswith("vip_check:"))
async def vip_check(call: CallbackQuery):

    user_id = call.from_user.id

    # =========================
    # SIMULASI PAYMENT CHECK
    # =========================
    paid = False  # <-- nanti ganti webhook / DB check

    if paid:
        PAID_VIP_USERS.add(user_id)

        await call.message.edit_text(
            "✅ <b>VIP ACTIVATED</b>\n\n"
            "🎉 Selamat kamu sekarang VIP!\n",
            parse_mode="HTML"
        )

        # =========================
        # NOTIF ADMIN
        # =========================
        await call.bot.send_message(
            ADMIN_ID,
            f"💎 VIP PAID\nUser: {user_id}"
        )

    else:
        await call.answer("⏳ Payment belum terdeteksi", show_alert=True)


# =========================
# VIP CANCEL
# =========================
@router.callback_query(F.data == "vip_cancel")
async def vip_cancel(call: CallbackQuery):

    await call.message.edit_text(
        "❌ <b>VIP CLOSED</b>\n\n"
        "😏 Mungkin lain kali.",
        parse_mode="HTML"
    )

    await call.answer()
# =========================
# ADMIN CONFIG (PRO MAX)
# =========================
SUPERADMINS = {6847035364}
ADMINS = set(SUPERADMINS)

ADMIN_LOG = []
CMD_LOCK = {}

# =========================
# ADMIN CHECK
# =========================
def is_admin(user_id: int):
    return user_id in ADMINS


def is_superadmin(user_id: int):
    return user_id in SUPERADMINS


# =========================
# LOG SYSTEM
# =========================
def log_admin(action, actor, target=None):
    ADMIN_LOG.append({
        "action": action,
        "actor": actor,
        "target": target,
        "time": time.time()
    })


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
# ADD ADMIN (SAFE MAX)
# =========================
@router.message(F.text.startswith("/addadmin"))
async def add_admin(message: Message):

    uid = message.from_user.id

    if not is_admin(uid):
        return await message.answer("🚫 ACCESS DENIED")

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

    ADMINS.add(new_id)
    log_admin("ADD_ADMIN", uid, new_id)

    await message.answer(f"💀 ADMIN ADDED\nID: {new_id}")


# =========================
# REMOVE ADMIN (SUPER SAFE)
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

    await message.answer(f"💀 ADMIN REMOVED\nID: {target}")


# =========================
# STATISTICS MAX
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


# =========================
# BROADCAST MAX (CHUNK + SAFE)
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

    # =========================
    # CHUNK SEND (ANTI FLOOD MAX)
    # =========================
    batch_size = 30

    for i in range(0, total, batch_size):

        batch = users[i:i+batch_size]

        for u in batch:
            try:
                await message.bot.send_message(u["user_id"], text)
                sent += 1
            except:
                failed += 1

        percent = ((i + batch_size) / total) * 100

        try:
            await status.edit_text(
                f"📡 <b>BROADCAST RUNNING</b>\n\n"
                f"👥 Total   : {total}\n"
                f"📤 Sent    : {sent}\n"
                f"❌ Failed  : {failed}\n"
                f"⏳ Progress: {min(percent,100):.1f}%"
            )
        except:
            pass

        await asyncio.sleep(1.0)  # stable throttle

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
# HELP KEYBOARD UI
# =========================
def help_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Upload", callback_data="help:upload"),
                InlineKeyboardButton(text="📥 Get File", callback_data="help:get")
            ],
            [
                InlineKeyboardButton(text="👤 Account", callback_data="help:account"),
                InlineKeyboardButton(text="💎 VIP", callback_data="help:vip")
            ],
            [
                InlineKeyboardButton(text="🛠 Admin", callback_data="help:admin")
            ],
            [
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="menu:start")
            ]
        ]
    )


# =========================
# HELP COMMAND
# =========================
@router.message(F.text == "/help")
async def help_cmd(message: Message):

    await message.answer(
        "🔥 <b>HELP CENTER</b>\n\nPilih menu di bawah 👇",
        parse_mode="HTML",
        reply_markup=help_kb()
    )


@router.message(F.text == "❓ Help")
async def help_button(message: Message):

    await message.answer(
        "🔥 <b>HELP CENTER</b>\n\nPilih menu 👇",
        parse_mode="HTML",
        reply_markup=help_kb()
    )


# =========================
# HELP ROUTER
# =========================
@router.callback_query(F.data.startswith("help:"))
async def help_router(call: CallbackQuery):

    menu = call.data.split(":")[1]

    if menu == "upload":
        text = (
            "📤 <b>UPLOAD FILE</b>\n\n"
            "1. Klik Up File\n"
            "2. Kirim media\n"
            "3. Klik DONE\n"
            "4. Dapat CODE"
        )

    elif menu == "get":
        text = (
            "📥 <b>GET FILE</b>\n\n"
            "1. Klik Get File\n"
            "2. Kirim CODE\n"
            "3. File otomatis dikirim"
        )

    elif menu == "account":
        text = (
            "👤 <b>ACCOUNT</b>\n\n"
            "• ID User\n"
            "• Username\n"
            "• Statistik File"
        )

    elif menu == "vip":
        text = (
            "💎 <b>VIP SYSTEM</b>\n\n"
            "⚡ Unlimited Upload\n"
            "⚡ Fast Access\n"
            "⚡ Priority System\n\n"
            "Gunakan /vip untuk upgrade"
        )

    elif menu == "admin":

        if not is_admin(call.from_user.id):
            return await call.answer("NO ACCESS", show_alert=True)

        text = (
            "🛠 <b>ADMIN PANEL</b>\n\n"
            "/stat → statistik\n"
            "/broadcast → kirim pesan\n"
            "/addadmin → tambah admin\n"
            "/deladmin → hapus admin"
        )

    else:
        text = "❌ Menu tidak ditemukan"

    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=help_kb()
    )

    await call.answer()


# =========================
# BACK TO MAIN MENU
# =========================
@router.callback_query(F.data == "menu:start")
async def back_to_start(call: CallbackQuery):

    await call.message.edit_text(
        "🔥 <b>MAIN MENU</b>\n\nPilih menu di bawah 👇",
        parse_mode="HTML",
        reply_markup=help_kb()
    )

    await call.answer()

# =========================
# STARTUP (UPGRADED PRODUCTION VERSION)
# =========================
async def main():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN tidak ditemukan")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL tidak ditemukan")

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    # =========================
    # INIT SAFE SHUTDOWN FLAG
    # =========================
    shutdown_event = asyncio.Event()

    # =========================
    # WEBHOOK CLEANUP
    # =========================
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    print(f"🤖 LOGIN: @{me.username}")

    # =========================
    # INIT DATABASE
    # =========================
    await init_db()
    print("🗄 DATABASE READY")

    # =========================
    # BACKGROUND TASKS (SAFE TRACKING)
    # =========================
    tasks = set()

    cleanup_task_runner = asyncio.create_task(cleanup_sessions())
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
        log_level="info",
        loop="asyncio"
    )

    server = uvicorn.Server(config)

    try:
        print("🚀 BOT STARTING...")

        await asyncio.gather(
            dp.start_polling(bot),
            server.serve()
        )

    except asyncio.CancelledError:
        print("⚠️ TASK CANCELLED")

    except Exception as e:
        print("❌ BOT ERROR:", repr(e))

    finally:
        print("💀 SHUTDOWN INITIATED")

        # =========================
        # STOP BACKGROUND TASKS
        # =========================
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        # =========================
        # CLOSE DATABASE
        # =========================
        try:
            if db_pool:
                await db_pool.close()
                print("🗄 DB CLOSED")
        except Exception as e:
            print("DB CLOSE ERROR:", e)

        # =========================
        # CLOSE BOT SESSION
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
        print("👋 MANUAL STOP (CTRL+C)")
