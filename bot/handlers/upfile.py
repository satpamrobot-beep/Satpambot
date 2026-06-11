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

    if uid in SESSION:
        return await call.answer("⛔ Upload masih berjalan", show_alert=True)

    SESSION[uid] = {
        "media": []
    }

    await state.set_state(UploadState.collecting)

    await call.message.edit_text(
        "📤 <b>UPLOAD MODE</b>\n\nKirim media sebanyak mungkin.\nKlik DONE kalau selesai.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ DONE", callback_data="up_done")],
            [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
        ])
    )

    await call.answer()


# =========================
# RECEIVE MEDIA (BATCH SAFE NO FLOOD)
# =========================
@router.message(UploadState.collecting, F.content_type.in_({"photo", "video", "document"}))
async def receive(message: Message, state: FSMContext):

    uid = message.from_user.id

    if uid not in SESSION:
        return

    sess = SESSION[uid]

    # detect type
    if message.photo:
        sess["media"].append(("photo", message.photo[-1].file_id))
    elif message.video:
        sess["media"].append(("video", message.video.file_id))
    else:
        sess["media"].append(("doc", message.document.file_id))

    # ONLY 1 NOTIF (UPDATE, NOT NEW MSG)
    if "msg" not in sess:
        sess["msg"] = await message.answer("📦 Media diterima... 1")
    else:
        await sess["msg"].edit_text(f"📦 Media diterima... {len(sess['media'])}")


# =========================
# DONE
# =========================
@router.callback_query(F.data == "up_done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess or not sess["media"]:
        return await call.answer("❌ Tidak ada media", show_alert=True)

    photos = sum(1 for x in sess["media"] if x[0] == "photo")
    videos = sum(1 for x in sess["media"] if x[0] == "video")
    docs = sum(1 for x in sess["media"] if x[0] == "doc")

    await state.update_data(
        media=sess["media"],
        photo=photos,
        video=videos,
        doc=docs
    )

    await state.set_state(UploadState.choose_type)

    await call.message.edit_text(
        f"📊 Total media: {len(sess['media'])}\n\nPilih tipe:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 FREE", callback_data="type_free"),
                InlineKeyboardButton(text="💰 PAID", callback_data="type_paid")
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

    SESSION.pop(uid, None)
    await state.clear()

    await call.message.edit_text("❌ Upload dibatalkan")
    await call.answer()


# =========================
# TYPE
# =========================
@router.callback_query(F.data.in_({"type_free", "type_paid"}))
async def type(call: CallbackQuery, state: FSMContext):

    is_paid = call.data == "type_paid"
    await state.update_data(is_paid=is_paid)

    if is_paid:
        await state.set_state(UploadState.price)
        await call.message.edit_text("💰 Masukkan harga (1000 - 50000)")
    else:
        await state.update_data(price=0)
        await state.set_state(UploadState.share)

        await call.message.edit_text(
            "🔗 Share mode:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
                    InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
                ]
            ])
        )

    await call.answer()


# =========================
# PRICE
# =========================
@router.message(UploadState.price)
async def price(message: Message, state: FSMContext):

    try:
        p = int(message.text)
    except:
        return await message.answer("❌ angka invalid")

    if p < 1000 or p > 50000:
        return await message.answer("❌ 1000 - 50000")

    await state.update_data(price=p)

    await state.set_state(UploadState.share)

    await message.answer(
        "🔗 Share mode:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
                InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
            ]
        ])
    )


# =========================
# SHARE + REVIEW
# =========================
@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    data["share"] = call.data == "share_yes"

    await state.update_data(share=data["share"])
    await state.set_state(UploadState.review)

    text = (
        "📋 REVIEW\n\n"
        f"Media: {len(data.get('media', []))}\n"
        f"Type: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price', 0)}\n"
        f"Share: {data['share']}\n\n"
        "EDIT / SAVE"
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💾 SAVE", callback_data="save_upload")],
            [InlineKeyboardButton(text="✏️ EDIT", callback_data="upfile")],
            [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
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

    code = f"earnfilebot_{rand(16)}_{build_media_tag(photos, videos, docs)}"

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO uploads (
                code, user_id, username,
                media, is_paid, price, is_share
            ) VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        code,
        uid,
        user.username,
        len(media),
        data.get("is_paid", False),
        data.get("price", 0),
        data.get("share", False)
        )

    SESSION.pop(uid, None)
    await state.clear()

    await call.message.edit_text(
        "🎉 MEDIA SUCCESS SAVED\n\n"
        f"Code: <code>{code}</code>\n"
        f"Total: {len(media)} media\n"
        f"Type: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Share: {data.get('share')}\n"
        f"User: @{user.username or 'hidden'}"
    )

    await call.answer()
