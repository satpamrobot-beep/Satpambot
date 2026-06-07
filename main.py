# =========================
# IMPORT
# =========================

import os
import re
import time
import asyncio
import json
import hmac
import hashlib
import httpx
import asyncio
import random
import secrets
import string
import uvicorn
import asyncpg

from datetime import datetime, timedelta
from fastapi import Request
from fastapi import FastAPI, Request
from dotenv import load_dotenv

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

from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramRetryAfter
)
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
PAYGG_SECRET = os.getenv("PAYGG_SECRET")
PAYGG_API_KEY = os.getenv("PAYGG_API_KEY")
UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL")
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL", 0))
VIP_LINK = os.getenv("VIP_LINK")

# =========================
# DB POOL
# =========================

db_pool: asyncpg.Pool | None = None


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
        CREATE TABLE IF NOT EXISTS users(
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            fullname TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS codes(
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE,
            owner_id BIGINT,
            buyer_id BIGINT,
            price BIGINT DEFAULT 0,
            is_paid BOOLEAN DEFAULT FALSE,
            total_media INT,
            total_size BIGINT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS medias(
            id SERIAL PRIMARY KEY,
            code TEXT,
            file_id TEXT,
            file_type TEXT,
            file_size BIGINT
        );

        CREATE TABLE IF NOT EXISTS transactions(
            id SERIAL PRIMARY KEY,
            order_id TEXT UNIQUE,
            user_id BIGINT,
            code TEXT,
            amount BIGINT,
            fee BIGINT,
            net BIGINT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS wallets(
            user_id BIGINT PRIMARY KEY,
            saldo BIGINT DEFAULT 0,
            total_pending BIGINT DEFAULT 0,
            total_process BIGINT DEFAULT 0,
            total_failed BIGINT DEFAULT 0,
            total_success BIGINT DEFAULT 0
        );
        """)
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

app = FastAPI()

# =========================
# ANTI SPAM + RATE LIMIT SYSTEM
# =========================

GLOBAL_DELAY = 0.08
last_global_send = 0

USER_DELAY = 1.5


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
    diff = now - last_global_send

    if diff < GLOBAL_DELAY:
        await asyncio.sleep(GLOBAL_DELAY - diff)

    last_global_send = time.time()


async def safe_send(func, *args, **kwargs):
    """
    SAFE TELEGRAM SENDER
    - anti flood
    - retry handling
    - stable for broadcast + payment notif
    """

    for attempt in range(5):
        try:
            await global_throttle()
            return await func(*args, **kwargs)

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

        except TelegramBadRequest as e:
            print("BAD REQUEST:", e)
            return None

        except Exception as e:
            print(f"ERROR attempt {attempt+1}:", e)
            await asyncio.sleep(1 + attempt)

    return None


# =========================
# ROUTER
# =========================

router = Router()
    
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

async def check_force_sub(bot: Bot, user_id: int, channel=FORCE_CHANNEL):
    try:
        member = await bot.get_chat_member(
            chat_id=channel,
            user_id=user_id
        )

        return member.status in ("member", "administrator", "creator")

    except Exception as e:
        print("FORCE SUB ERROR:", e)
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
# CREATE QRIS INVOICE (5 MIN EXPIRE)
# =========================
async def create_qris(order_id: str, amount: int):
    expires_at = datetime.utcnow() + timedelta(minutes=5)

    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.post(
            "https://api.paygg.example/create-invoice",
            headers={"Authorization": f"Bearer {PAYGG_API_KEY}"},
            json={
                "order_id": order_id,
                "amount": amount,
                "method": "qris",
                "expired_at": expires_at.isoformat()
            }
        )

    data = res.json()

    return {
        "qr_url": data.get("qr_url"),
        "expires_at": expires_at,
        "order_id": order_id
    }


# =========================
# SEND QR (EMBED DI BOT)
# =========================
async def send_qr(user_id, qr_url, caption):
    msg = await bot.send_photo(
        chat_id=user_id,
        photo=qr_url,
        caption=caption
    )
    return msg.message_id


# =========================
# AUTO DELETE EXPIRED QR
# =========================
async def qr_expire_watcher():
    while True:
        async with db_pool.acquire() as conn:

            expired = await conn.fetch(
                """
                SELECT user_id, message_id, order_id
                FROM payments
                WHERE status='pending'
                AND expires_at < NOW()
                """
            )

            for p in expired:

                try:
                    await bot.delete_message(
                        chat_id=p["user_id"],
                        message_id=p["message_id"]
                    )
                except:
                    pass

                await conn.execute(
                    "UPDATE payments SET status='expired' WHERE order_id=$1",
                    p["order_id"]
                )

        await asyncio.sleep(10)


# =========================
# WEBHOOK (FULL CORE SYSTEM)
# =========================
@app.post("/webhook")
async def webhook(request: Request):

    raw_body = await request.body()

    try:
        data = json.loads(raw_body)
    except:
        return {"ok": False}

    order_id = data.get("order_id")
    status = data.get("status")
    amount = int(data.get("amount") or 0)

    signature = request.headers.get("X-Signature", "")

    if not order_id:
        return {"ok": False}

    if status not in ("paid", "failed", "expired"):
        return {"ok": True}

    if not verify_signature(raw_body, signature):
        return {"ok": False, "error": "invalid_signature"}

    async with db_pool.acquire() as conn:

        async with conn.transaction():

            payment = await conn.fetchrow(
                """
                SELECT order_id, user_id, code, status, group_message_id
                FROM payments
                WHERE order_id=$1
                FOR UPDATE
                """,
                order_id
            )

            if not payment:
                return {"ok": False}

            if payment["status"] == "paid":
                return {"ok": True}

            user_id = payment["user_id"]
            code = payment["code"]
            msg_id = payment["group_message_id"]

            # =========================
            # UPDATE STATUS
            # =========================
            await conn.execute(
                "UPDATE payments SET status=$1 WHERE order_id=$2",
                status, order_id
            )

            # =========================
            # SUCCESS FLOW
            # =========================
            if status == "paid":

                # unlock code
                await conn.execute(
                    "UPDATE codes SET owner_id=$1 WHERE code=$2",
                    user_id, code
                )

                # wallet
                await conn.execute(
                    """
                    UPDATE wallets
                    SET saldo = saldo + $1,
                        total_success = total_success + $1
                    WHERE user_id=$2
                    """,
                    amount, user_id
                )

                # referral 10%
                ref = await conn.fetchrow(
                    "SELECT ref_by FROM users WHERE user_id=$1",
                    user_id
                )

                if ref and ref["ref_by"]:
                    bonus = int(amount * 0.1)

                    await conn.execute(
                        """
                        UPDATE wallets
                        SET saldo = saldo + $1,
                            referral_income = referral_income + $1
                        WHERE user_id=$2
                        """,
                        bonus, ref["ref_by"]
                    )

    # =========================
    # UPDATE GROUP MESSAGE
    # =========================
    try:
        if status == "paid":
            icon = "🟢 SUCCESS"
        elif status == "expired":
            icon = "⚫ EXPIRED"
        else:
            icon = "🟡 PROCESS"

        await bot.edit_message_text(
            chat_id=NOTIFICATION_CHANNEL,
            message_id=msg_id,
            text=(
                "┌───────────────┐\n"
                f"│ {icon}\n"
                "├───────────────┤\n"
                f"│ User : {user_id}\n"
                f"│ Code : {code}\n"
                "└───────────────┘"
            )
        )
    except:
        pass

    # =========================
    # USER ACTION
    # =========================
    try:
        if status == "paid":
            await bot.delete_message(user_id, payment["message_id"])

            medias = await db_pool.fetch(
                "SELECT file_id, file_type FROM medias WHERE code=$1",
                code
            )

            for m in medias:
                if m["file_type"] == "photo":
                    await bot.send_photo(user_id, m["file_id"])
                elif m["file_type"] == "video":
                    await bot.send_video(user_id, m["file_id"])
                else:
                    await bot.send_document(user_id, m["file_id"])

            await bot.send_message(
                user_id,
                f"🟢 SUCCESS\nCode: <code>{code}</code>",
                parse_mode="HTML"
            )

        elif status == "expired":
            await bot.delete_message(user_id, payment["message_id"])
            await bot.send_message(user_id, "⚫ QRIS EXPIRED")

    except:
        pass

    return {"ok": True}
    
# =========================
# START
# =========================

@router.message(CommandStart())
async def start(message: Message, bot: Bot):

    user = message.from_user

    # =========================
    # SAVE USER
    # =========================
    try:
        await add_user(
            user.id,
            user.username or "ghost",
            user.full_name
        )
    except Exception as e:
        print("ADD USER ERROR:", e)

    # =========================
    # ANTI SPAM
    # =========================
    if not user_limit(user.id):
        return await safe_send(
            message.answer,
            "⏳ Santai dulu bos… jangan spam kayak lagi panik 😏"
        )

    # =========================
    # FORCE SUB CHECK
    # =========================
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
                    "Tanpa itu, bot ini bukan buat kamu.\n\n"
                    "👉 Join dulu baru balik lagi."
                ),
                reply_markup=force_kb()
            )

    # =========================
    # MAIN MENU (SAVAGE UI)
    # =========================
    await safe_send(
        message.answer,
        (
            "🔥 <b>FILE CODE SYSTEM</b>\n\n"
            "━━━━━━━━━━━━━━\n"
            "😈 STATUS: ONLINE & WATCHING YOU\n"
            "━━━━━━━━━━━━━━\n\n"
            "📌 MENU\n"
            "━━━━━━━━━━━━━━\n"
            "📤 Upload File → masukin file\n"
            "📥 Get File → pakai CODE\n\n"
            "━━━━━━━━━━━━━━\n"
            "💀 WARNING\n"
            "━━━━━━━━━━━━━━\n"
            "• CODE itu bukan mainan\n"
            "• Salah kirim = tanggung sendiri\n"
            "• Bot ini gak punya tombol 'kasihan'\n\n"
            "😏 Selamat bermain… jangan nangis kalau salah langkah."
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
            "⏳ Pelan dikit… kamu bukan robot 😏",
            show_alert=True
        )

    if not FORCE_CHANNEL:
        return await call.answer(
            "Force Sub OFF",
            show_alert=True
        )

    joined = await check_force_sub(
        bot,
        user_id,
        FORCE_CHANNEL
    )

    if not joined:
        return await call.answer(
            "🚫 Belum join. Jangan bohong 😏",
            show_alert=True
        )

    try:
        await call.message.edit_text(
            "✅ VERIFIED\n\n"
            "😏 Oke… kamu ternyata masih layak masuk."
        )
    except:
        pass

    await safe_send(
        call.message.answer,
        (
            "🔥 AKSES DIBUKA\n\n"
            "😈 Selamat… kamu lolos gerbang.\n"
            "Sekarang jangan bikin masalah."
        ),
        reply_markup=get_keyboard()
    )

    await call.answer("Ya… kamu lolos 😏")
# =========================
# UP FILE INIT
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


@router.message(F.text == "📤 Up File")
async def up_file(message: Message):

    user_id = message.from_user.id

    # =========================
    # ANTI SPAM
    # =========================
    if not user_limit(user_id):
        return await safe_send(
            message.answer,
            "⏳ Jangan spam ya 😏"
        )

    # =========================
    # RESET SESSION
    # =========================
    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    # =========================
    # CREATE SESSION
    # =========================
    user_states[user_id] = {"mode": "upload"}

    upload_sessions[user_id] = {
        "video": 0,
        "photo": 0,
        "document": 0,
        "items": [],
        "msg_id": None,
        "created_at": time.time()
    }

    # =========================
    # SEND PANEL
    # =========================
    msg = await safe_send(
        message.answer,
        (
            "📤 <b>UPLOAD MODE AKTIF</b>\n\n"
            "😏 Kirim file kamu sekarang.\n"
            "Klik DONE kalau sudah selesai.\n\n"
            "💀 Jangan kelamaan..."
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

    state = user_states.get(user_id)
    session = upload_sessions.get(user_id)

    # =========================
    # VALIDATION
    # =========================
    if not state or state.get("mode") != "upload":
        return

    if not session or not session.get("msg_id"):
        return

    # =========================
    # GET FILE
    # =========================
    file_obj = None
    file_type = None

    if message.photo:
        file_obj = message.photo[-1]
        file_type = "photo"
        session["photo"] = session.get("photo", 0) + 1

    elif message.video:
        file_obj = message.video
        file_type = "video"
        session["video"] = session.get("video", 0) + 1

    elif message.document:
        file_obj = message.document
        file_type = "document"
        session["document"] = session.get("document", 0) + 1

    if not file_obj:
        return

    # =========================
    # SAVE ITEM
    # =========================
    session["items"].append({
        "file_id": file_obj.file_id,
        "type": file_type,
        "size": getattr(file_obj, "file_size", 0) or 0
    })

    # =========================
    # DELETE USER MESSAGE
    # =========================
    try:
        await message.delete()
    except:
        pass

    # =========================
    # THROTTLE EDIT
    # =========================
    now = time.time()
    last = last_edit_time.get(user_id, 0)

    if now - last < 1.3:
        return

    last_edit_time[user_id] = now

    # =========================
    # STATS
    # =========================
    total = len(session["items"])
    size_mb = round(
        sum(x.get("size", 0) for x in session["items"]) / (1024 * 1024),
        2
    )

    bar_len = 10
    filled = min(bar_len, total)
    bar = "█" * filled + "░" * (bar_len - filled)

    text = (
        "📤 <b>UPLOAD PROGRESS</b>\n\n"
        f"📊 Progress : [{bar}] {total} file\n\n"
        f"🖼 Photo    : {session['photo']}\n"
        f"🎬 Video    : {session['video']}\n"
        f"📁 Doc      : {session['document']}\n"
        f"💾 Size     : {size_mb} MB\n\n"
        "━━━━━━━━━━━━━━\n"
        "😏 Klik DONE kalau sudah selesai"
    )

    # =========================
    # UPDATE PANEL
    # =========================
    try:
        await safe_send(
            message.bot.edit_message_text,
            chat_id=message.chat.id,
            message_id=session["msg_id"],
            text=text,
            parse_mode="HTML",
            reply_markup=upload_kb()
        )
    except Exception as e:
        print("EDIT ERROR:", e)

GROUP_ID = -1003920865154

# =========================
# GENERATE CODE
# =========================
def generate_code(v, p, d):
    base = f"{v}{p}{d}{secrets.token_hex(4)}"
    rand = hashlib.sha1(base.encode()).hexdigest()[:12]
    return f"decodefilebot_{v}v_{p}p_{d}d_{rand}"


# =========================
# START DONE FLOW
# =========================
@router.callback_query(F.data == "upload_done")
async def done(call: CallbackQuery):

    user_id = call.from_user.id
    s = upload_sessions.get(user_id)

    if not s or not s.get("items"):
        return await call.answer("😏 kosong? mau jual angin?", show_alert=True)

    if s.get("locked"):
        return await call.answer("⏳ lagi diproses...", show_alert=True)

    # 🔥 LOCK TOTAL (ANTI SPAM / DOUBLE CLICK)
    s["locked"] = True
    s["step"] = "title"
    s["created_at"] = int(time.time())

    await call.message.edit_text(
        "━━━━━━━━━━━━━━\n"
        "💀 <b>MARKET SETUP</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "📝 Kirim <b>JUDUL PRODUCT</b>\n"
        "😏 contoh: Premium Pack",
        parse_mode="HTML"
    )


# =========================
# FLOW ENGINE (STATE SAFE)
# =========================
@router.message(F.text)
async def market_flow(message: Message):

    user_id = message.from_user.id
    s = upload_sessions.get(user_id)

    if not s or not s.get("locked"):
        return

    # prevent other bots trigger / noise
    if message.text.startswith("/"):
        return

    text = message.text.strip()

    # =========================
    # STEP 1 TITLE
    # =========================
    if s["step"] == "title":
        s["title"] = text
        s["step"] = "paid"

        return await message.answer("💰 BERBAYAR? (YES / NO)")

    # =========================
    # STEP 2 PAID
    # =========================
    if s["step"] == "paid":

        if text.lower() == "yes":
            s["paid"] = True
            s["step"] = "price"
            return await message.answer("💵 MASUKKAN HARGA (angka)")

        s["paid"] = False
        s["price"] = 0
        s["step"] = "final"
        return await message.answer("📤 SHARE MEDIA? (YES / NO)")

    # =========================
    # STEP 3 PRICE
    # =========================
    if s["step"] == "price":

        if not text.isdigit():
            return await message.answer("❌ angka saja")

        s["price"] = int(text)
        s["step"] = "final"
        return await message.answer("📤 SHARE MEDIA? (YES / NO)")


    # =========================
    # STEP 4 FINAL BUILD
    # =========================
    if s["step"] == "final":

        s["share"] = text.lower() == "yes"

        code = generate_code(
            s.get("video", 0),
            s.get("photo", 0),
            s.get("document", 0)
        )

        total_items = len(s["items"])
        total_size = sum(x.get("size", 0) for x in s["items"])

        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():

                    # =========================
                    # SAVE PRODUCT META
                    # =========================
                    await conn.execute(
                        """
                        INSERT INTO codes(
                            code, owner_id, title,
                            is_paid, price, share_media,
                            total_media, total_size,
                            status, created_at
                        )
                        VALUES($1,$2,$3,$4,$5,$6,$7,$8,'PENDING',NOW())
                        """,
                        code,
                        user_id,
                        s["title"],
                        s["paid"],
                        s["price"],
                        s["share"],
                        total_items,
                        total_size
                    )

                    # =========================
                    # SAVE MEDIA
                    # =========================
                    items = [
                        (code, m["file_id"], m["type"], m.get("size", 0))
                        for m in s["items"]
                        if m.get("file_id")
                    ]

                    if items:
                        await conn.executemany(
                            """
                            INSERT INTO medias(code,file_id,file_type,file_size)
                            VALUES($1,$2,$3,$4)
                            """,
                            items
                        )

            # =========================
            # POST TO GROUP (ANTI SPAM ONLY 1 MSG)
            # =========================
            group_msg = await message.bot.send_message(
                GROUP_ID,
                (
                    "━━━━━━━━━━━━━━\n"
                    "🟡 <b>NEW PRODUCT (PENDING)</b>\n"
                    "━━━━━━━━━━━━━━\n\n"
                    f"📦 CODE : <code>{code[:10]}****</code>\n"
                    f"📝 TITLE: {s['title']}\n"
                    f"💰 TYPE : {'PAID' if s['paid'] else 'FREE'}\n"
                    f"💵 PRICE: {s['price']}\n"
                    f"👤 USER : {user_id}\n\n"
                    "⚠️ STATUS: WAITING PAYMENT\n"
                    "━━━━━━━━━━━━━━"
                ),
                parse_mode="HTML"
            )

            # OPTIONAL STORE GROUP MSG ID
            async with db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE codes SET group_msg_id=$1 WHERE code=$2",
                    group_msg.message_id,
                    code
                )

            await message.answer(
                "💀 PRODUCT CREATED\n\n"
                f"📦 CODE: <code>{code}</code>\n"
                f"📝 TITLE: {s['title']}\n"
                f"⚡ STATUS: READY TO SELL",
                parse_mode="HTML"
            )

        except Exception as e:
            print("ERROR:", e)
            await message.answer("❌ gagal proses")

        # =========================
        # CLEAN + STERILIZE SESSION
        # =========================
        upload_sessions.pop(user_id, None)
        user_states.pop(user_id, None)
        last_edit_time.pop(user_id, None)


# =========================
# CANCEL RESET
# =========================
@router.callback_query(F.data == "upload_cancel")
async def cancel(call: CallbackQuery):

    user_id = call.from_user.id

    upload_sessions.pop(user_id, None)
    user_states.pop(user_id, None)
    last_edit_time.pop(user_id, None)

    await call.message.edit_text("❌ SYSTEM RESET DONE")

# =========================
# CONFIG
# =========================
COOLDOWN_TIME = 5

# WAJIB ADA INI (BIAR GAK ERROR)
cooldown = {
    "global": {}
}


# =========================
# NORMALIZER (FIX + SAFE)
# =========================
def normalize_type(t: str):
    t = (t or "").lower().strip()

    if t in ("photo", "image", "img", "jpg", "jpeg", "png"):
        return "photo"

    if t in ("video", "vid", "mp4", "mov"):
        return "video"

    return "document"


# =========================
# COOLDOWN (ANTI SPAM FIX)
# =========================
def is_cooldown(user_id: int) -> bool:
    now = time.time()
    last = cooldown["global"].get(user_id, 0)

    if now - last < COOLDOWN_TIME:
        return True

    cooldown["global"][user_id] = now
    return False


# =========================
# LOAD MEDIA (SAFE + SUPABASE READY)
# =========================
async def load_media(code: str):
    if not code:
        return []

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT file_id, file_type, COALESCE(file_size, 0) AS file_size
                FROM medias
                WHERE code = $1
                ORDER BY id ASC
                """,
                code
            )

    except Exception as e:
        print("DB ERROR load_media:", e)
        return []

    if not rows:
        return []

    return [
        {
            "file_id": r["file_id"],
            "file_type": normalize_type(r["file_type"]),
            "file_size": int(r["file_size"] or 0)
        }
        for r in rows
    ]

# =========================
# SEND MEDIA (ANTI BAN + SAFE + STABLE)
# =========================
async def send_media(bot, chat_id: int, chunk: list):

    if not chunk:
        return False

    media = []

    # =========================
    # BUILD MEDIA GROUP (MAX 10 TELEGRAM LIMIT FIX)
    # =========================
    for m in chunk[:10]:

        fid = m.get("file_id")
        ftype = (m.get("file_type") or "").lower()

        if not fid:
            continue

        try:
            if ftype == "photo":
                media.append(InputMediaPhoto(media=fid))

            elif ftype == "video":
                media.append(InputMediaVideo(media=fid))

            else:
                media.append(InputMediaDocument(media=fid))

        except Exception as e:
            print("MEDIA BUILD ERROR:", e)

    if not media:
        return False

    # =========================
    # SEND WITH RETRY + FLOOD CONTROL
    # =========================
    for attempt in range(5):

        try:
            await global_throttle()  # optional anti spam global limiter

            await bot.send_media_group(
                chat_id=chat_id,
                media=media
            )

            return True

        except TelegramRetryAfter as e:
            wait = int(e.retry_after or 1)
            print(f"FLOOD WAIT: {wait}s")
            await asyncio.sleep(wait + 1)

        except TelegramBadRequest as e:
            print("BAD REQUEST:", e)
            return False

        except Exception as e:
            print(f"SEND MEDIA ERROR [{attempt+1}]:", e)
            await asyncio.sleep(1 + attempt)

    print("❌ FAILED SEND MEDIA AFTER RETRIES")
    return False

# =========================
# GLOBAL SAFE STATE
# =========================
COOLDOWN_TIME = 5
pagination_lock = {}
page_history = {}

cooldown = {"global": {}}


# =========================
# NORMALIZER
# =========================
def normalize_type(t: str):
    t = (t or "").lower().strip()
    if t in ["photo", "image", "img"]:
        return "photo"
    if t in ["video", "vid"]:
        return "video"
    return "document"


# =========================
# COOLDOWN SAFE
# =========================
def is_cooldown(user_id: int):
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
# SAFE MEDIA SENDER (ANTI FLOOD + ANTI BAN)
# =========================
async def send_media(bot, chat_id: int, chunk: list):

    if not chunk:
        return False

    media = []

    for m in chunk[:5]:

        fid = m.get("file_id")
        ftype = normalize_type(m.get("file_type"))

        if not fid:
            continue

        try:
            if ftype == "photo":
                media.append(InputMediaPhoto(media=fid))

            elif ftype == "video":
                media.append(InputMediaVideo(media=fid))

            else:
                media.append(InputMediaDocument(media=fid))

        except Exception as e:
            print("MEDIA BUILD ERROR:", e)

    if not media:
        return False

    for attempt in range(5):

        try:
            await asyncio.sleep(0.3)  # throttle ringan biar gak spam API

            await bot.send_media_group(
                chat_id=chat_id,
                media=media
            )
            return True

        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)

        except TelegramBadRequest as e:
            print("BAD REQUEST:", e)
            return False

        except Exception as e:
            print(f"SEND MEDIA ERROR {attempt+1}:", e)
            await asyncio.sleep(1 + attempt)

    return False


# =========================
# KEYBOARD
# =========================
def build_kb(user_id, page, total_pages):

    history = page_history.get(user_id, set())
    rows = []

    rows.append([
        InlineKeyboardButton(
            text="⬅ Prev" if page > 0 else "⛔ Prev",
            callback_data="prev" if page > 0 else "noop"
        ),
        InlineKeyboardButton(
            text="➡ Next" if page < total_pages - 1 else "⛔ Next",
            callback_data="next" if page < total_pages - 1 else "noop"
        )
    ])

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

    rows.append([
        InlineKeyboardButton(
            text="📢 CHANNEL",
            url="https://t.me/+3g_yhHwxCrc5ZTg9"
        ),
        InlineKeyboardButton(
            text="💬 GROUP",
            url="https://t.me/+1tipdp-NTywzODhl"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# =========================
# RENDER PAGE (FIX SAFE)
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

    total_pages = max(1, (len(data) + size - 1) // size)

    page = max(0, min(page, total_pages - 1))
    state["page"] = page

    start = page * size
    end = start + size
    chunk = data[start:end]

    page_history.setdefault(user_id, set()).add(page)

    await send_media(bot, chat_id, chunk)

    text = (
        f"📦 CODE: <code>{state.get('code','-')}</code>\n"
        f"📄 Page: {page+1}/{total_pages}\n"
        f"📁 Media: {start+1}-{start+len(chunk)} / {len(data)}\n\n"
        "👇 CONTROL PANEL"
    )

    kb = build_kb(user_id, page, total_pages)

    panel_id = state.get("last_panel_msg")

    if panel_id:
        try:
            await bot.delete_message(chat_id, panel_id)
        except:
            pass

    msg = await bot.send_message(
        chat_id,
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    state["last_panel_msg"] = msg.message_id


# =========================
# PAGINATION LOCK
# =========================
@router.callback_query(
    F.data.in_(["next", "prev"]) |
    F.data.startswith("page:")
)
async def pagination(call):

    user_id = call.from_user.id

    if pagination_lock.get(user_id):
        return await call.answer()

    pagination_lock[user_id] = True

    try:
        state = user_states.get(user_id)
        if not state:
            return await call.answer("Session expired", show_alert=True)

        data = state.get("data") or []
        if not data:
            return await call.answer("No data", show_alert=True)

        old_page = state.get("page", 0)
        size = state.get("page_size", 5)

        max_page = (len(data) - 1) // size

        if call.data == "next":
            page = old_page + 1
        elif call.data == "prev":
            page = old_page - 1
        else:
            try:
                page = int(call.data.split(":")[1])
            except:
                return await call.answer("Error")

        page = max(0, min(page, max_page))

        if page == old_page:
            return await call.answer()

        state["page"] = page

        await render_page(
            user_id,
            call.bot,
            call.message.chat.id
        )

        await call.answer()

    finally:
        pagination_lock.pop(user_id, None)


# =========================
# NOOP
# =========================
@router.callback_query(F.data == "noop")
async def noop(call):
    await call.answer("😏")

# =========================
# START GET FILE
# =========================
@router.message(F.text == "📥 Get File")
async def start_get(message: Message):

    user_id = message.from_user.id

    user_states[user_id] = {
        "mode": "getfile",
        "created_at": time.time()
    }

    await message.answer("📥 Kirim CODE 😏")


# =========================
# RECEIVE CODE (FIXED + SAFE)
# =========================
@router.message(F.text & ~F.text.startswith("/"))
async def receive_code(message: Message):

    user_id = message.from_user.id
    state = user_states.get(user_id)

    if not state or state.get("mode") != "getfile":
        return

    # =========================
    # COOLDOWN PROTECTION
    # =========================
    if is_cooldown(user_id):
        return await message.answer("⏳ Jangan spam")

    text = message.text or ""

    # =========================
    # FIXED CODE PATTERN
    # =========================
    codes = re.findall(
        r"\bdecodefilebot_[A-Za-z0-9v_pd_]+\b",
        text
    )

    if not codes:
        return await message.answer("❌ CODE tidak valid")

    codes = list(dict.fromkeys(codes))[:3]

    all_data = []

    # =========================
    # LOAD MULTI CODE (SAFE)
    # =========================
    for code in codes:

        data = await load_media(code)

        if data:
            all_data.extend(data)

        await asyncio.sleep(0.1)  # anti flood DB

    if not all_data:
        return await message.answer("❌ File tidak ditemukan")

    all_data = all_data[:50]  # limit safety

    # =========================
    # DELETE OLD PANEL SAFE
    # =========================
    old_state = user_states.get(user_id)

    if old_state and old_state.get("last_panel_msg"):

        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=old_state["last_panel_msg"]
            )
        except:
            pass

    # =========================
    # CREATE VIEW SESSION
    # =========================
    user_states[user_id] = {
        "mode": "view",
        "code": codes[0],
        "page": 0,
        "page_size": 5,
        "data": all_data,
        "last_panel_msg": None,
        "created_at": time.time()
    }

    page_history[user_id] = set()

    await message.answer(
        f"📦 FILE DITEMUKAN: <b>{len(all_data)}</b>",
        parse_mode="HTML"
    )

    # =========================
    # RENDER FIRST PAGE
    # =========================
    await render_page(
        user_id,
        message.bot,
        message.chat.id
    )
# ======================
# USER SYSTEM PRO
# ======================

import time

# optional in-memory anti spam tracking
user_cache = {}
USER_COOLDOWN = 3  # detik


# ======================
# ADD / UPDATE USER (PRO)
# ======================
async def add_user(user_id: int, username: str = None, fullname: str = None):

    username = username or ""
    fullname = fullname or ""
    now = int(time.time())

    # ======================
    # SIMPLE ANTI-SPAM CACHE
    # ======================
    last = user_cache.get(user_id, 0)
    if now - last < USER_COOLDOWN:
        return False  # skip spam insert/update

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
                VALUES ($1,$2,$3,NOW(),NOW())

                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    fullname = EXCLUDED.fullname,
                    last_seen = NOW()
                """,
                user_id,
                username,
                fullname
            )

        return True

    except Exception as e:
        print("ADD USER ERROR:", e)
        return False

# =========================
# ACCOUNT DASHBOARD (FULL SYSTEM)
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

        # =========================
        # INIT WALLET SAFE
        # =========================
        await conn.execute("""
            INSERT INTO wallets (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id)

        # =========================
        # GET WALLET
        # =========================
        wallet = await conn.fetchrow("""
            SELECT * FROM wallets WHERE user_id=$1
        """, user.id)

        # =========================
        # GET RECENT CODES
        # =========================
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

    # =========================
    # SAFE PARSE WALLET
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

    # =========================
    # FORMAT CODE LIST
    # =========================
    if codes:
        code_text = "\n\n".join(
            f"📦 <code>{c['code']}</code>\n"
            f"📁 File: {c['total_media']} | 💾 Size: {(c['total_size'] or 0)/1048576:.2f} MB\n"
            f"⚡ Status: {c['status']}"
            for c in codes
        )
    else:
        code_text = "❌ Belum ada code"

    username = f"@{user.username}" if user.username else "Tidak ada"

    # =========================
    # MAIN TEXT
    # =========================
    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>ACCOUNT DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🆔 ID       : <code>{user.id}</code>\n"
        f"👤 Name     : {user.full_name}\n"
        f"🔗 Username : {username}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "💰 WALLET BALANCE\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"💵 Saldo   : Rp {saldo:,}\n"
        f"🟡 Pending : Rp {pending:,}\n"
        f"🔵 Process : Rp {process:,}\n"
        f"🔴 Failed  : Rp {failed:,}\n"
        f"🟢 Success : Rp {success:,}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🏦 BANK ACCOUNT\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"Bank  : {bank_name}\n"
        f"No    : {bank_number}\n"
        f"Owner : {bank_owner}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📱 EWALLET (INDONESIA)\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"Type : {ewallet_type}\n"
        f"No   : {ewallet_number}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🌍 GLOBAL PAYMENT\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"Type    : {global_type}\n"
        f"Account : {global_account}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📊 STATISTIC\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"📦 Total Code : {total_codes}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "📁 RECENT CODES\n"
        "━━━━━━━━━━━━━━━━━━\n"

        f"{code_text}\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "⚙️ MENU SYSTEM\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "💳 /deposit - Top up saldo (QRIS / Bank / Ewallet)\n"
        "🏧 /withdraw - Tarik saldo ke bank/ewallet\n"
        "🏦 /setbank - Atur bank\n"
        "📱 /setewallet - Atur ewallet\n"
        "🌍 /setglobal - Atur global wallet (PayPal/USDT)\n"
    )

    await message.answer(text, parse_mode="HTML")

# =========================
# WALLET KEYBOARD
# =========================

from datetime import datetime

def saldo_kb():

    now = datetime.now()

    wd_open = 8 <= now.hour < 20

    text = (
        "💸 Withdraw"
        if wd_open
        else "🔒 Withdraw"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data="withdraw"
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
# /SALDO (WALLET DASHBOARD)
# =========================

from datetime import datetime
from aiogram import F
from aiogram.types import Message


@router.message(F.text == "/saldo")
async def saldo_cmd(message: Message):

    user_id = message.from_user.id

    try:

        async with db_pool.acquire() as conn:

            # =========================
            # GET WALLET DATA (SAFE)
            # =========================
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

        # =========================
        # SAFE DEFAULT
        # =========================
        saldo = row["saldo"] if row else 0
        pending = row["pending"] if row else 0
        process = row["process"] if row else 0
        failed = row["failed"] if row else 0
        success = row["success"] if row else 0

        # =========================
        # TOTAL AKUMULASI
        # =========================
        total = saldo + pending + process + failed + success

        # =========================
        # WITHDRAW STATUS (TIME WINDOW)
        # =========================
        now_hour = datetime.now().hour

        wd_open = 8 <= now_hour < 20

        status = "🟢 OPEN" if wd_open else "🔴 CLOSED"

        # =========================
        # TEXT OUTPUT
        # =========================
        text = (
            "━━━━━━━━━━━━━━\n"
            "💰 <b>WALLET DASHBOARD</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            f"💵 <b>Saldo Utama</b>\n"
            f"Rp {saldo:,}\n\n"

            "━━━━━━━━━━━━━━\n"

            f"🟡 Pending : Rp {pending:,}\n"
            f"🔄 Process : Rp {process:,}\n"
            f"❌ Failed  : Rp {failed:,}\n"
            f"✅ Success : Rp {success:,}\n\n"

            "━━━━━━━━━━━━━━\n"

            f"📊 <b>Total Akumulasi</b>\n"
            f"Rp {total:,}\n\n"

            "━━━━━━━━━━━━━━\n"

            f"⏰ Withdraw Status : {status}\n"
            "🕗 Jam Operasional : 08:00 - 20:00 WIB\n\n"

            "━━━━━━━━━━━━━━\n"
            "📋 <b>INFO WITHDRAW</b>\n"
            "━━━━━━━━━━━━━━\n\n"

            "💸 Minimal Withdraw : Rp 10.000\n"
            "💸 Maksimal Withdraw : Rp 500.000\n\n"

            "⚠️ RULES:\n"
            "• Saldo harus cukup\n"
            "• 1 request aktif per user\n"
            "• Diproses sesuai antrian\n"
            "• Salah input rekening bukan tanggung jawab sistem\n"
            "• Withdraw di luar jam kerja otomatis ditolak\n"
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=saldo_kb()  # tombol deposit/withdraw (kalau ada)
        )

    except Exception as e:
        print("SALDO ERROR:", e)

        await message.answer("❌ Gagal memuat saldo, coba lagi nanti")

# =========================
# CONFIG
# =========================
GROUP_ID = -1003920865154
MIN_WITHDRAW = 50000

# =========================
# STORAGE (SIMPLE SAFE MODE)
# =========================
AUDIT_LOG = []
PROCESSED_TX = set()
ACTIVE_LOCK = {}

# =========================
# ADMIN CHECK (SIMPLE)
# =========================
ADMIN_IDS = {6847035364}

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# AUDIT LOG
# =========================
def log_action(actor_id, action, target_id=None):
    AUDIT_LOG.append({
        "actor": actor_id,
        "action": action,
        "target": target_id,
        "time": time.time()
    })


# =========================
# USER INIT
# =========================
async def add_user(user_id, username, fullname):
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id, username, fullname)
            VALUES($1,$2,$3)
            ON CONFLICT(user_id)
            DO UPDATE SET username=$2, fullname=$3
            """,
            user_id, username, fullname
        )


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
            total_success,
            bank_name,
            bank_number,
            bank_owner
        )
        VALUES ($1,0,0,0,'','','')
        ON CONFLICT (user_id) DO NOTHING
        """,
        user_id
    )


# =========================
# ADD BALANCE (DEPOSIT)
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
# CREATE WITHDRAW (USER)
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
# ADMIN PANEL
# =========================
@router.message(F.text == "/admin")
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        return await message.answer("🚫 NO ACCESS")

    await message.answer(
        "🛠 ADMIN PANEL ACTIVE\n\n/menu:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📥 Withdraw List", callback_data="wd_list")
            ],
            [
                InlineKeyboardButton(text="📜 Audit Log", callback_data="audit")
            ]
        ])
    )


# =========================
# WITHDRAW LIST
# =========================
@router.message(F.text == "/withdrawlist")
async def withdraw_list(message: Message):

    if not is_admin(message.from_user.id):
        return

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM withdraw_requests WHERE status='PENDING' ORDER BY id ASC LIMIT 20"
        )

    if not rows:
        return await message.answer("📭 No request")

    for r in rows:

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ APPROVE", callback_data=f"wd_ok:{r['id']}"),
                InlineKeyboardButton(text="❌ REJECT", callback_data=f"wd_no:{r['id']}")
            ]
        ])

        await message.answer(
            f"🏧 WITHDRAW REQUEST\n\n"
            f"User: {r['user_id']}\n"
            f"Amount: Rp {r['amount']:,}\n"
            f"Bank: {r['bank_name']}",
            reply_markup=kb
        )


# =========================
# APPROVE WITHDRAW (BUY STYLE GROUP)
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

        PROCESSED_TX.add(req_id)
        ACTIVE_LOCK.pop(req["user_id"], None)

        await conn.execute(
            "UPDATE withdraw_requests SET status='APPROVED' WHERE id=$1",
            req_id
        )

        await conn.execute(
            """
            UPDATE wallets
            SET total_pending = total_pending - $2,
                total_success = total_success + $2
            WHERE user_id=$1
            """,
            req["user_id"], req["amount"]
        )

    # =========================
    # BUY STYLE GROUP MESSAGE
    # =========================
    text = (
        "━━━━━━━━━━━━━━\n"
        "💰 TRANSACTION SUCCESS\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🆔 User ID   : {req['user_id']}\n"
        f"💸 Type      : WITHDRAW\n"
        f"💵 Amount    : Rp {req['amount']:,}\n"
        f"🏦 Method    : BANK TRANSFER\n\n"
        "━━━━━━━━━━━━━━\n"
        "🟢 STATUS    : APPROVED\n"
        f"⏰ Time      : {time.strftime('%H:%M WIB')}\n"
        "━━━━━━━━━━━━━━"
    )

    await call.message.bot.send_message(GROUP_ID, text)

    log_action(call.from_user.id, "APPROVE_WITHDRAW", req["user_id"])

    await call.message.edit_text(f"✅ APPROVED ID {req_id}")


# =========================
# REJECT WITHDRAW (BUY STYLE GROUP)
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

        await conn.execute(
            """
            UPDATE wallets
            SET saldo = saldo + $2,
                total_pending = total_pending - $2
            WHERE user_id=$1
            """,
            req["user_id"], req["amount"]
        )

        await conn.execute(
            "UPDATE withdraw_requests SET status='REJECTED' WHERE id=$1",
            req_id
        )

    # =========================
    # BUY STYLE GROUP MESSAGE
    # =========================
    text = (
        "━━━━━━━━━━━━━━\n"
        "💰 TRANSACTION FAILED\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🆔 User ID   : {req['user_id']}\n"
        f"💸 Type      : WITHDRAW\n"
        f"💵 Amount    : Rp {req['amount']:,}\n"
        f"🏦 Method    : BANK TRANSFER\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔴 STATUS    : REJECTED\n"
        "💡 Reason    : Manual review\n"
        f"⏰ Time      : {time.strftime('%H:%M WIB')}\n"
        "━━━━━━━━━━━━━━"
    )

    await call.message.bot.send_message(GROUP_ID, text)

    log_action(call.from_user.id, "REJECT_WITHDRAW", req["user_id"])

    await call.message.edit_text(f"❌ REJECTED ID {req_id}")
        
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
# BROADCAST (DEWA VERSION)
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

        except Exception:
            failed += 1

        # =========================
        # SMART DELAY (ANTI BANNED)
        # =========================
        if i % 20 == 0:
            await asyncio.sleep(1.2)  # heavy pause
        else:
            await asyncio.sleep(random.uniform(0.03, 0.1))  # normal delay

        # =========================
        # UPDATE PROGRESS (SETIAP 25 USER)
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
            except:
                pass

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
# HELP TEXT
# =========================
HELP_TEXT = """
<b>🔥 TZY FILE BOT — HELP MENU 🔥</b>

Selamat datang di <b>TZY FILE BOT</b>
Bot untuk upload & ambil file pakai <code>CODE</code>

━━━━━━━━━━━━━━
📤 <b>UPLOAD FILE</b>
━━━━━━━━━━━━━━
1. Tekan <b>📤 Up File</b>
2. Kirim media
3. Tekan <b>✅ DONE</b>
4. Bot kasih CODE

⚠️ Jangan lupa DONE!

━━━━━━━━━━━━━━
📥 <b>GET FILE</b>
━━━━━━━━━━━━━━
1. Tekan <b>📥 Get File</b>
2. Kirim CODE
3. File dikirim otomatis

❌ Kalau error:
• CODE salah
• Tidak ditemukan

━━━━━━━━━━━━━━
👤 <b>ACCOUNT</b>
━━━━━━━━━━━━━━
• ID
• Nama
• Username

━━━━━━━━━━━━━━
💎 <b>VIP</b>
━━━━━━━━━━━━━━
⚡ Unlimited Upload  
⚡ Faster Access  
⚡ Priority System  

━━━━━━━━━━━━━━
🛠 <b>ADMIN</b>
━━━━━━━━━━━━━━
<code>/stat</code> → statistik  
<code>/broadcast</code> → kirim ke semua user  
<code>/addadmin</code> → tambah admin  

━━━━━━━━━━━━━━
⚠ <b>RULE</b>
━━━━━━━━━━━━━━
❌ Spam  
❌ Abuse  
❌ Flood  

━━━━━━━━━━━━━━
💀 <b>NOTE</b>
━━━━━━━━━━━━━━
• Bot bukan cenayang 😏  
• Salah input = salah sendiri  
• Simpan CODE baik-baik  

━━━━━━━━━━━━━━
🚀 <b>READY</b>
━━━━━━━━━━━━━━
"""

# =========================
# HELP HANDLER
# =========================
@router.message(F.text == "/help")
async def help_cmd(message: Message):

    await asyncio.sleep(0.2)

    await message.answer(
        HELP_TEXT,
        parse_mode="HTML"
    )


@router.message(F.text == "❓ Help")
async def help_button(message: Message):

    await asyncio.sleep(0.2)

    await message.answer(
        HELP_TEXT,
        parse_mode="HTML"
    )

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

                page_cooldown.pop(uid, None)

                user_click_lock.pop(uid, None)

# =========================
# STARTUP
# =========================
async def main():

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN tidak ditemukan")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL tidak ditemukan")

    # =========================
    # INIT BOT
    # =========================
    bot = Bot(BOT_TOKEN)

    # HAPUS WEBHOOK LAMA
    await bot.delete_webhook(
        drop_pending_updates=True
    )

    me = await bot.get_me()

    print(f"🤖 LOGIN: @{me.username}")

    dp = Dispatcher()
    dp.include_router(router)

    # =========================
    # DATABASE
    # =========================
    await init_db()

    # =========================
    # BACKGROUND TASK
    # =========================
    asyncio.create_task(cleanup_task())

    print("🔥 BOT STARTED")
    print("🚀 START POLLING")

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

    try:

        await asyncio.gather(
            dp.start_polling(bot),
            server.serve()
        )

    except Exception as e:

        print("❌ BOT ERROR:", repr(e))

    finally:

        print("💀 SHUTDOWN")

        try:
            if db_pool:
                await db_pool.close()
        except Exception as e:
            print("DB CLOSE ERROR:", e)

        try:
            await bot.session.close()
        except Exception as e:
            print("BOT CLOSE ERROR:", e)


# =========================
# RUN
# =========================
if __name__ == "__main__":
    asyncio.run(main())
