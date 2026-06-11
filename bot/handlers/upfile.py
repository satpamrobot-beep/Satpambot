import asyncio
import string
import random

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.pool import get_pool

router = Router()

# =========================
# SESSION LOCK (ANTI FLOOD + MULTI MEDIA SAFE)
# =========================
SESSION = {}

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
# CODE GENERATOR (PERSISTENT SAFE)
# =========================
def rand(n=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


def build_media_tag(photo=0, video=0, doc=0):
    out = []
    if photo: out.append(f"{photo}p")
    if video: out.append(f"{video}v")
    if doc: out.append(f"{doc}d")
    return "_".join(out)


# =========================
# PROGRESS REAL (NO FLOOD EDIT)
# =========================
async def progress(msg: Message, text: str):
    bar = ["▱▱▱▱▱", "▰▱▱▱▱", "▰▰▱▱▱", "▰▰▰▱▱", "▰▰▰▰▱", "▰▰▰▰▰"]

    for i in range(6):
        await asyncio.sleep(0.12)
        await msg.edit_text(f"{text}\n\n{bar[i]}\n{i*20}%")

# =========================
# START UPLOAD
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    # =========================
    # CLEAN STUCK SESSION
    # =========================
    if uid in SESSION:
        session = SESSION.get(uid)

        # kalau session rusak / kosong → hapus
        if not session or not session.get("active"):
            SESSION.pop(uid, None)
        else:
            return await call.answer("⛔ Upload masih berjalan", show_alert=True)

    # =========================
    # INIT SESSION (SAFE MODE)
    # =========================
    SESSION[uid] = {
        "active": True,
        "media": [],
        "status": "collecting"
    }

    await state.set_state(UploadState.collecting)

    await call.message.edit_text(
        "📤 <b>UPLOAD MODE</b>\n\n"
        "📌 Kirim media sebanyak mungkin (foto / video / dokumen)\n"
        "⚡ Bot akan menghitung otomatis\n\n"
        "Klik <b>DONE</b> kalau sudah selesai upload.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ DONE", callback_data="up_done")],
            [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
        ])
    )

    await call.answer()
# =========================
# RECEIVE MEDIA (BATCH SAFE NO FLOOD)
# =========================
import time

@router.message(UploadState.collecting, F.content_type.in_({"photo", "video", "document"}))
async def receive(message: Message, state: FSMContext):

    uid = message.from_user.id

    if uid not in SESSION:
        return

    sess = SESSION[uid]

    # =========================
    # DETECT MEDIA TYPE
    # =========================
    if message.photo:
        sess["media"].append(("photo", message.photo[-1].file_id))

    elif message.video:
        sess["media"].append(("video", message.video.file_id))

    elif message.document:
        sess["media"].append(("doc", message.document.file_id))

    total = len(sess["media"])

    # =========================
    # INIT MESSAGE ONCE
    # =========================
    if not sess.get("msg"):
        sess["msg"] = await message.answer(
            f"📦 <b>UPLOAD BERJALAN</b>\n\n"
            f"📊 Media: <b>{total}</b>"
        )
        sess["last_update"] = total
        sess["last_edit_time"] = time.time()
        return

    # =========================
    # ANTI FLOOD + DEBOUNCE SYSTEM
    # =========================
    last = sess.get("last_update", 0)
    last_time = sess.get("last_edit_time", 0)

    now = time.time()

    # UPDATE RULE:
    # - hanya update kalau bertambah
    # - minimal jeda 0.8 detik (anti spam Telegram)
    if total > last and (now - last_time) > 0.8:

        try:
            await sess["msg"].edit_text(
                f"📦 <b>UPLOAD BERJALAN</b>\n\n"
                f"📊 Media: <b>{total}</b>\n"
                f"⚡ Status: uploading..."
            )

            sess["last_update"] = total
            sess["last_edit_time"] = now

        except:
            # fallback kalau edit kena flood limit
            try:
                sess["msg"] = await message.answer(
                    f"📦 Media diterima: {total}"
                )
            except:
                pass
# =========================
# DONE
# =========================
@router.callback_query(F.data == "up_done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    # =========================
    # VALIDATION
    # =========================
    if not sess or not sess.get("media"):
        return await call.answer("❌ Tidak ada media", show_alert=True)

    # prevent double click / spam DONE
    if sess.get("done_locked"):
        return await call.answer("⏳ Sedang diproses...", show_alert=True)

    sess["done_locked"] = True

    # =========================
    # COUNT MEDIA
    # =========================
    media_list = sess["media"]

    photos = 0
    videos = 0
    docs = 0

    for m in media_list:
        if m[0] == "photo":
            photos += 1
        elif m[0] == "video":
            videos += 1
        elif m[0] == "doc":
            docs += 1

    # =========================
    # SAVE TO FSM (CLEAN STRUCTURE)
    # =========================
    await state.update_data(
        media=media_list,
        photo=photos,
        video=videos,
        doc=docs,
        total=len(media_list)
    )

    await state.set_state(UploadState.choose_type)

    # =========================
    # UPDATE UI
    # =========================
    await call.message.edit_text(
        "📊 <b>REVIEW UPLOAD</b>\n\n"
        f"📦 Total media : <b>{len(media_list)}</b>\n"
        f"🖼 Photo       : {photos}\n"
        f"🎥 Video       : {videos}\n"
        f"📄 Document    : {docs}\n\n"
        "👉 Pilih tipe file:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 FREE", callback_data="type_free"),
                InlineKeyboardButton(text="💰 PAID", callback_data="type_paid")
            ],
            [
                InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")
            ]
        ])
    )

    await call.answer()
# =========================
# CANCEL (CLEAR ALL)
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    # =========================
    # CLEAR SESSION SAFELY
    # =========================
    SESSION.pop(uid, None)
    await state.clear()

    # =========================
    # NOTIF MELAYANG (POPUP)
    # =========================
    await call.answer("❌ Upload berhasil dibatalkan", show_alert=True)

    # =========================
    # BACK TO HOME (DASHBOARD)
    # =========================
    from handlers.start import dashboard_text, dashboard_kb
    from db.users import get_user_balance

    balance = await get_user_balance(uid)

    try:
        await call.message.edit_text(
            dashboard_text(call.from_user, balance),
            reply_markup=dashboard_kb()
        )
    except:
        # fallback kalau message tidak bisa diedit
        await call.message.answer(
            dashboard_text(call.from_user, balance),
            reply_markup=dashboard_kb()
        )
# =========================
# TYPE
# =========================
@router.callback_query(F.data.in_({"type_free", "type_paid"}))
async def type_handler(call: CallbackQuery, state: FSMContext):

    # =========================
    # SAFE DATA CHECK
    # =========================
    data = await state.get_data()

    # prevent double click / resend bug
    if data.get("type_locked"):
        return await call.answer("⏳ Diproses...", show_alert=True)

    await state.update_data(type_locked=True)

    is_paid = call.data == "type_paid"
    await state.update_data(is_paid=is_paid)

    # =========================
    # PAID FLOW
    # =========================
    if is_paid:

        await state.set_state(UploadState.price)

        await call.message.edit_text(
            "💰 <b>SET HARGA FILE</b>\n\n"
            "Masukkan harga:\n"
            "Min: 1000\nMax: 50000\n\n"
            "Contoh: 5000 = Rp 5.000"
        )

    # =========================
    # FREE FLOW
    # =========================
    else:

        await state.update_data(price=0)
        await state.set_state(UploadState.share)

        await call.message.edit_text(
            "🔗 <b>SHARE MODE</b>\n\nPilih akses file:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
                    InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
                ],
                [
                    InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")
                ]
            ])
        )

    await call.answer()
# =========================
# PRICE
# =========================
@router.message(UploadState.price)
async def price_handler(message: Message, state: FSMContext):

    text = message.text.strip()

    # =========================
    # VALIDATE NUMBER
    # =========================
    if not text.isdigit():
        return await message.answer("❌ Harga harus angka")

    price = int(text)

    # =========================
    # RANGE VALIDATION
    # =========================
    if price < 1000 or price > 50000:
        return await message.answer("❌ Min 1000 - Max 50000")

    # =========================
    # SAVE PRICE
    # =========================
    await state.update_data(price=price)

    # =========================
    # MOVE TO NEXT STEP
    # =========================
    await state.set_state(UploadState.share)

    await message.answer(
        "🔗 <b>SHARE MODE</b>\n\nPilih akses file:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
                InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
            ],
            [
                InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")
            ]
        ])
    )
# =========================
# SHARE + REVIEW
# =========================
@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share_handler(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    is_share = call.data == "share_yes"

    # =========================
    # SAFE UPDATE
    # =========================
    await state.update_data(share=is_share)
    await state.set_state(UploadState.review)

    media_count = len(data.get("media", []))

    type_file = "PAID" if data.get("is_paid") else "FREE"
    price = data.get("price", 0)

    share_text = "PUBLIC 🌍" if is_share else "PRIVATE 🔒"

    # =========================
    # REVIEW TEXT (CLEAN UI)
    # =========================
    text = (
        "📋 <b>REVIEW UPLOAD</b>\n\n"
        f"📦 Media   : <b>{media_count}</b>\n"
        f"💰 Type    : <b>{type_file}</b>\n"
        f"💵 Price   : <b>Rp {price:,.0f}</b>\n"
        f"🔗 Share   : <b>{share_text}</b>\n\n"
        "⚠️ Pastikan semua sudah benar sebelum SAVE"
    )

    # =========================
    # ACTION BUTTONS
    # =========================
    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 SAVE", callback_data="save_upload")
            ],
            [
                InlineKeyboardButton(text="✏️ EDIT", callback_data="upfile")
            ],
            [
                InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")
            ]
        ])
    )

    await call.answer()
# =========================
# SAVE (PERSIST DB + MULTI MEDIA CODE)
# =========================
@router.callback_query(F.data == "save_upload")
async def save(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    user = call.from_user
    data = await state.get_data()

    media = data.get("media", [])

    photos = data.get("photo", 0)
    videos = data.get("video", 0)
    docs = data.get("doc", 0)

    # =========================
    # CODE GENERATOR (PERSISTENT SAFE)
    # =========================
    import random, string

    def rand(n=16):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

    def build_media_tag(p, v, d):
        parts = []
        if p: parts.append(f"{p}p")
        if v: parts.append(f"{v}v")
        if d: parts.append(f"{d}d")
        return "_".join(parts)

    code = f"earnfilebot_{rand(12)}_{build_media_tag(photos, videos, docs)}"

    # =========================
    # SAVE DB
    # =========================
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO uploads (
                code, user_id, username,
                media, photo_count, video_count, doc_count,
                is_paid, price, is_share, created_at
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
        """,
        code,
        uid,
        user.username,
        media,
        photos,
        videos,
        docs,
        data.get("is_paid", False),
        data.get("price", 0),
        data.get("share", False)
        )

    # =========================
    # CLEAN SESSION
    # =========================
    SESSION.pop(uid, None)
    await state.clear()

    # =========================
    # FORMAT UI CLEAN
    # =========================
    is_paid = data.get("is_paid", False)
    price = data.get("price", 0)
    is_share = data.get("share", False)

    price_text = f"💵 Price : {price}" if is_paid else ""
    share_text = "🔓 Public" if is_share else "🔒 Private"

    await call.message.edit_text(
        "🎉 <b>MEDIA SUCCESS SAVED</b>\n\n"
        f"🔑Code  : <code>{code}</code>\n"
        f"📦Total : {len(media)} media\n"
        f"🚨Sistem: {'PAID' if is_paid else 'FREE'}\n"
        f"{price_text}\n"
        f"{share_text}\n"
        f"Create By @{user.username or 'hidden'}"
    )

    await call.answer()
