import asyncio
import random
import time
import json
import re

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.pool import get_pool

router = Router()

SESSION = {}
UPLOAD_LOCKS = {}

MAX_MEDIA = 100
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    collecting = State()
    choose_type = State()
    price = State()
    share = State()
    review = State()


# =========================
# UTILS
# =========================
def rand(n=14):
    return ''.join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=n))


def build_media_tag(p=0, v=0, d=0):
    parts = []
    if p: parts.append(f"{p}p")
    if v: parts.append(f"{v}v")
    if d: parts.append(f"{d}d")
    return "_".join(parts)


def human_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


# =========================
# KEYBOARD
# =========================
UPLOAD_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ DONE", callback_data="up_done")],
    [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
])

def kb_type():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆓 FREE", callback_data="type_free"),
            InlineKeyboardButton(text="💰 PAID", callback_data="type_paid")
        ],
        [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
    ])

def kb_visibility():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
            InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
        ]
    ])

def kb_save():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 SAVE TO CLOUD", callback_data="save_upload")]
    ])


# =========================
# START UPLOAD
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    # =========================
    # GLOBAL LOCK (ANTI SPAM CLICK)
    # =========================
    lock = UPLOAD_LOCKS.setdefault(uid, asyncio.Lock())

    if lock.locked():
        return await call.answer()

    async with lock:

        # =========================
        # SESSION CHECK
        # =========================
        sess = SESSION.get(uid)

        if sess and sess.get("active"):
            return await call.answer("⛔ Masih ada sesi upload aktif", show_alert=True)

        # =========================
        # RESET OLD DATA
        # =========================
        SESSION.pop(uid, None)

        # =========================
        # CREATE NEW SESSION
        # =========================
        SESSION[uid] = {
            "active": True,
            "media": [],
            "msg": None,
            "done": False,
            "created": time.time(),
            "expire": time.time() + 600  # 10 menit
        }

        # =========================
        # SET STATE
        # =========================
        await state.set_state(UploadState.collecting)

        # =========================
        # SAFE EDIT / SEND PANEL
        # =========================
        try:
            msg = await call.message.edit_text(
                "📁 <b>UPLOAD MODE</b>\n\n"
                f"📦 Total: 0/{MAX_MEDIA}\n"
                "👇 Kirim file kamu",
                reply_markup=UPLOAD_KB,
                parse_mode="HTML"
            )
        except:
            # fallback kalau gagal edit
            msg = await call.message.answer(
                "📁 <b>UPLOAD MODE</b>\n\n"
                f"📦 Total: 0/{MAX_MEDIA}\n"
                "👇 Kirim file kamu",
                reply_markup=UPLOAD_KB,
                parse_mode="HTML"
            )

        SESSION[uid]["msg"] = msg

        await call.answer()


# =========================
# RECEIVE MEDIA
# =========================
@router.message(UploadState.collecting, F.photo | F.video | F.document)
async def receive(message: Message, state: FSMContext):

    uid = message.from_user.id

    # =========================
    # LOCK USER (ANTI FLOOD)
    # =========================
    lock = UPLOAD_LOCKS.setdefault(uid, asyncio.Lock())

    async with lock:

        # =========================
        # SESSION VALIDATION
        # =========================
        sess = SESSION.get(uid)
        if not sess or not sess.get("active"):
            return

        if sess.get("done"):
            return

        media_list = sess.setdefault("media", [])

        # =========================
        # STATE VALIDATION
        # =========================
        current = await state.get_state()
        if current != UploadState.collecting:
            return

        # =========================
        # LIMIT JUMLAH FILE
        # =========================
        if len(media_list) >= MAX_MEDIA:
            try:
                await message.delete()
            except:
                pass
            return

        file_type = None
        file_id = None
        file_size = 0

        # =========================
        # DETECT FILE
        # =========================
        if message.photo:
            f = message.photo[-1]
            file_type = "photo"
            file_id = f.file_id
            file_size = f.file_size or 0

        elif message.video:
            f = message.video
            file_type = "video"
            file_id = f.file_id
            file_size = f.file_size or 0

        elif message.document:
            f = message.document
            file_type = "doc"
            file_id = f.file_id
            file_size = f.file_size or 0

        # =========================
        # VALIDATE SIZE PER FILE
        # =========================
        if file_size and file_size > MAX_FILE_SIZE:
            return await message.reply("❌ File terlalu besar")

        # =========================
        # VALIDATE TOTAL SIZE
        # =========================
        total_size = sum(x[2] for x in media_list) + file_size
        if total_size > MAX_TOTAL_SIZE:
            return await message.reply("❌ Total size melebihi limit")

        # =========================
        # SAVE
        # =========================
        media_list.append((file_type, file_id, file_size))

        # =========================
        # COUNT (SAFE)
        # =========================
        p = v = d = 0
        for x in media_list:
            try:
                if x[0] == "photo":
                    p += 1
                elif x[0] == "video":
                    v += 1
                elif x[0] == "doc":
                    d += 1
            except:
                continue

        # =========================
        # DELETE USER MSG (SAFE)
        # =========================
        try:
            await message.delete()
        except:
            pass

        # =========================
        # UPDATE PANEL (SAFE)
        # =========================
        msg = sess.get("msg")

        if msg:
            try:
                await msg.edit_text(
                    "📁 <b>UPLOAD MODE</b>\n\n"
                    f"📦 Total: {len(media_list)}/{MAX_MEDIA}\n"
                    f"🖼 Photo: {p}\n"
                    f"🎥 Video: {v}\n"
                    f"📄 Doc: {d}\n"
                    f"💾 Size: {human_size(total_size)}",
                    reply_markup=UPLOAD_KB,
                    parse_mode="HTML"
                )
            except:
                pass
# =========================
# DONE
# =========================
@router.callback_query(F.data == "up_done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    # =========================
    # SESSION VALIDATION
    # =========================
    sess = SESSION.get(uid)
    if not sess or not sess.get("active"):
        return await call.answer("⚠️ Session tidak valid", show_alert=True)

    media = sess.get("media", [])
    if not media:
        return await call.answer("⚠️ Media kosong", show_alert=True)

    # =========================
    # ANTI SPAM CLICK
    # =========================
    if sess.get("done_locked"):
        return await call.answer()

    sess["done_locked"] = True

    # =========================
    # STATE VALIDATION
    # =========================
    current = await state.get_state()
    if current != UploadState.uploading:
        sess["done_locked"] = False
        return await call.answer("⚠️ Flow tidak valid", show_alert=True)

    # =========================
    # PREVENT DOUBLE DONE
    # =========================
    if sess.get("done"):
        sess["done_locked"] = False
        return await call.answer("⚠️ Sudah diproses", show_alert=True)

    sess["done"] = True

    # =========================
    # COUNT MEDIA (SAFE)
    # =========================
    photo = 0
    video = 0
    doc = 0

    for m in media:
        try:
            if m[0] == "photo":
                photo += 1
            elif m[0] == "video":
                video += 1
            elif m[0] == "doc":
                doc += 1
        except:
            continue

    await state.update_data(
        media=media,
        photo=photo,
        video=video,
        doc=doc
    )

    await state.set_state(UploadState.choose_type)

    # =========================
    # SAFE EDIT
    # =========================
    try:
        await call.message.edit_text(
            "☁️ <b>UPLOAD SELESAI</b>\n\n💡 Pilih tipe:",
            reply_markup=kb_type(),
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer()

    # =========================
    # UNLOCK
    # =========================
    sess["done_locked"] = False
# =========================
# TYPE
# =========================
@router.callback_query(F.data.in_({"type_free", "type_paid"}))
async def type_handler(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    # =========================
    # SESSION VALIDATION
    # =========================
    sess = SESSION.get(uid)
    if not sess or not sess.get("active"):
        return await call.answer("⚠️ Session tidak valid", show_alert=True)

    # =========================
    # ANTI SPAM CLICK
    # =========================
    if sess.get("type_locked"):
        return await call.answer()

    sess["type_locked"] = True

    # =========================
    # STATE VALIDATION
    # =========================
    current = await state.get_state()
    if current != UploadState.choose_type:
        sess["type_locked"] = False
        return await call.answer("⚠️ Flow tidak valid", show_alert=True)

    # =========================
    # PROCESS
    # =========================
    is_paid = call.data == "type_paid"
    await state.update_data(is_paid=is_paid)

    try:
        if is_paid:
            await state.set_state(UploadState.price)

            await call.message.edit_text(
                "💰 <b>Masukkan harga:</b>",
                parse_mode="HTML"
            )

        else:
            await state.update_data(price=0)
            await state.set_state(UploadState.share)

            await call.message.edit_text(
                "🌍 <b>Pilih visibility:</b>",
                reply_markup=kb_visibility(),
                parse_mode="HTML"
            )

    except:
        pass

    await call.answer()

    # =========================
    # UNLOCK
    # =========================
    sess["type_locked"] = False
# =========================
# PRICE
# =========================
@router.message(UploadState.price)
async def price_handler(message: Message, state: FSMContext):

    uid = message.from_user.id

    # =========================
    # SESSION VALIDATION
    # =========================
    sess = SESSION.get(uid)
    if not sess or not sess.get("active"):
        return

    # =========================
    # ANTI SPAM INPUT
    # =========================
    if sess.get("price_locked"):
        return

    sess["price_locked"] = True

    # =========================
    # VALIDATE STATE
    # =========================
    current = await state.get_state()
    if current != UploadState.price:
        sess["price_locked"] = False
        return

    # =========================
    # PARSE INPUT
    # =========================
    text = message.text or ""
    price_text = re.sub(r"\D", "", text)

    if not price_text:
        sess["price_locked"] = False
        return await message.answer("❌ Masukkan angka yang valid")

    price = int(price_text)

    # =========================
    # VALIDASI RANGE
    # =========================
    if price < 1000:
        sess["price_locked"] = False
        return await message.answer("❌ Minimal Rp 1.000")

    if price > 1_000_000_000:
        sess["price_locked"] = False
        return await message.answer("❌ Maksimal Rp 1M")

    # =========================
    # SAVE DATA
    # =========================
    await state.update_data(price=price)
    await state.set_state(UploadState.share)

    # =========================
    # FORMAT RAPI
    # =========================
    formatted_price = f"Rp {price:,}".replace(",", ".")

    try:
        await message.answer(
            f"✅ Harga diset: <b>{formatted_price}</b>\n\n🌍 Pilih visibility:",
            reply_markup=kb_visibility(),
            parse_mode="HTML"
        )
    except:
        pass

    # =========================
    # UNLOCK
    # =========================
    sess["price_locked"] = False
# =========================
# SHARE + REVIEW
# =========================
@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share_handler(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    # ✅ ambil session (optional tapi penting buat kontrol)
    sess = SESSION.get(uid)
    if not sess or not sess.get("active"):
        return await call.answer("⚠️ Session tidak valid", show_alert=True)

    # ✅ anti spam klik
    if sess.get("share_locked"):
        return await call.answer()

    sess["share_locked"] = True

    # =========================
    # PROCESS
    # =========================
    is_public = call.data == "share_yes"
    await state.update_data(share=is_public)

    data = await state.get_data()

    # ✅ safe get (anti KeyError)
    is_paid = data.get("is_paid", False)
    price = data.get("price", 0)

    status = "💰 PAID" if is_paid else "🆓 FREE"

    await state.set_state(UploadState.review)

    text = f"""
📋 <b>REVIEW UPLOAD</b>

📌 Type : {status}
💳 Price : {price}
🌍 Share : {"PUBLIC" if is_public else "PRIVATE"}

👇 SAVE untuk lanjut
"""

    # =========================
    # SAFE EDIT (ANTI CRASH)
    # =========================
    try:
        await call.message.edit_text(
            text,
            reply_markup=kb_save(),
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer()
# =========================
# SAVE
# =========================
@router.callback_query(F.data == "save_upload")
async def save(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    user = call.from_user

    sess = SESSION.get(uid)

    # ✅ Anti double click
    if not sess or sess.get("saved"):
        return await call.answer("⚠️ Sudah disimpan", show_alert=True)

    sess["saved"] = True  # lock langsung

    data = await state.get_data()

    code = f"earnfilebot_{rand(14)}"

    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO uploads (
                    code,user_id,username,media,
                    photo_count,video_count,doc_count,
                    is_paid,price,is_share,created_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
                """,
                code,
                user.id,
                user.username or user.full_name,
                json.dumps(data["media"]),
                data["photo"],
                data["video"],
                data["doc"],
                data["is_paid"],
                data.get("price", 0),
                data["share"]
            )

    except Exception:
        # ❌ jangan expose error asli
        sess["saved"] = False  # unlock biar bisa retry
        return await call.message.edit_text("❌ Database error, coba lagi")

    # cleanup
    await state.clear()
    SESSION.pop(uid, None)
    UPLOAD_LOCKS.pop(uid, None)

    bot_username = (await call.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"

    # ✅ safe edit
    try:
        await call.message.edit_text(
f"""
🎉 <b>SUCCESS SAVE</b>

🔑 CODE:
<code>{code}</code>

💳 STATUS:
{"💰 PAID" if data["is_paid"] else "🆓 FREE"}

📁 MEDIA:
{"Public" if data["share"] else "Private"}

💰 PRICE:
{data.get("price", 0)}

🔗 LINK:
{link}
""",
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer()
# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    SESSION.pop(call.from_user.id, None)
    await state.clear()

    await call.message.edit_text("❌ Cancelled")
    await call.answer()
