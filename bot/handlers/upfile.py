import asyncio
import random
import string

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

# =========================
# ANTI DUPLICATE LOCK
# =========================
UPLOAD_LOCK = {}


# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    waiting_media = State()
    choose_type = State()
    enter_price = State()
    choose_share = State()
    review = State()


# =========================
# CODE GENERATOR
# =========================
def random_id(length: int = 14):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def build_media_part(photo=0, video=0, doc=0):
    parts = []

    if photo > 0:
        parts.append(f"{photo}p")
    if video > 0:
        parts.append(f"{video}v")
    if doc > 0:
        parts.append(f"{doc}d")

    return "_".join(parts)


def generate_code(user_id: int, photo=0, video=0, doc=0):
    base = random_id()
    media = build_media_part(photo, video, doc)

    if media:
        return f"earnfilebot_{base}_{media}"
    return f"earnfilebot_{base}"


# =========================
# UPLOAD START
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id

    if UPLOAD_LOCK.get(uid):
        return await call.answer("⛔ Upload masih berjalan", show_alert=True)

    UPLOAD_LOCK[uid] = True
    await state.set_state(UploadState.waiting_media)

    await call.message.edit_text(
        "📤 <b>Upload File</b>\n\nKirim media (foto/video/dokumen)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Cancel", callback_data="up_cancel")]
        ])
    )

    await call.answer()


# =========================
# RECEIVE MEDIA
# =========================
@router.message(UploadState.waiting_media, F.content_type.in_({"photo", "video", "document"}))
async def receive_media(message: Message, state: FSMContext):

    msg = await message.answer("📤 Uploading... 0%")

    file_id = None
    video_count = 0
    photo_count = 0
    doc_count = 0

    if message.photo:
        file_id = message.photo[-1].file_id
        photo_count = 1

    elif message.video:
        file_id = message.video.file_id
        video_count = 1

    else:
        file_id = message.document.file_id
        doc_count = 1

    # fake smooth progress (Telegram limitation)
    for i in range(0, 101, 20):
        await asyncio.sleep(0.15)
        await msg.edit_text(f"📤 Uploading...\n\n[{i}%]")

    await state.update_data(
        file_id=file_id,
        photo=photo_count,
        video=video_count,
        doc=doc_count
    )

    await msg.edit_text(
        "✅ Media received\n\nPilih tipe:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 Free", callback_data="type_free"),
                InlineKeyboardButton(text="💰 Paid", callback_data="type_paid")
            ],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="up_cancel")]
        ])
    )

    await state.set_state(UploadState.choose_type)


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    UPLOAD_LOCK[call.from_user.id] = False
    await state.clear()
    await call.message.edit_text("❌ Upload dibatalkan")
    await call.answer()


# =========================
# TYPE SELECT
# =========================
@router.callback_query(F.data.in_({"type_free", "type_paid"}))
async def choose_type(call: CallbackQuery, state: FSMContext):

    is_paid = call.data == "type_paid"
    await state.update_data(is_paid=is_paid)

    if is_paid:
        await call.message.edit_text("💰 Masukkan harga (1000 - 50000)")
        await state.set_state(UploadState.enter_price)

    else:
        await state.update_data(price=0)

        await call.message.edit_text(
            "🔗 Share mode:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌍 Public", callback_data="share_yes"),
                    InlineKeyboardButton(text="🔒 Private", callback_data="share_no")
                ]
            ])
        )

        await state.set_state(UploadState.choose_share)

    await call.answer()


# =========================
# PRICE INPUT
# =========================
@router.message(UploadState.enter_price)
async def price_input(message: Message, state: FSMContext):

    try:
        price = int(message.text)
    except:
        return await message.answer("❌ Angka tidak valid")

    if price < 1000 or price > 50000:
        return await message.answer("❌ Min 1000 - Max 50000")

    await state.update_data(price=price)

    await message.answer(
        "🔗 Share mode:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 Public", callback_data="share_yes"),
                InlineKeyboardButton(text="🔒 Private", callback_data="share_no")
            ]
        ])
    )

    await state.set_state(UploadState.choose_share)


# =========================
# SHARE MODE
# =========================
@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share_mode(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    data["is_share"] = call.data == "share_yes"

    await state.update_data(is_share=data["is_share"])

    text = (
        "📋 <b>Review Upload</b>\n\n"
        f"Type: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price', 0)}\n"
        f"Share: {'YES' if data['is_share'] else 'NO'}\n\n"
        "Klik SAVE untuk lanjut"
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💾 SAVE", callback_data="save_upload")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="up_cancel")]
        ])
    )

    await state.set_state(UploadState.review)
    await call.answer()


# =========================
# SAVE (DATABASE + CODE FIXED)
# =========================
@router.callback_query(F.data == "save_upload")
async def save_upload(call: CallbackQuery, state: FSMContext):

    user = call.from_user
    data = await state.get_data()

    # FIX MEDIA COUNT
    code = generate_code(
        user.id,
        data.get("photo", 0),
        data.get("video", 0),
        data.get("doc", 0)
    )

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO uploads (
                code, user_id, username,
                file_id, is_paid, price, is_share
            ) VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        code,
        user.id,
        user.username,
        data["file_id"],
        data.get("is_paid", False),
        data.get("price", 0),
        data.get("is_share", False)
        )

    UPLOAD_LOCK[user.id] = False
    await state.clear()

    await call.message.edit_text(
        "🎉 <b>Media Success Saved</b>\n\n"
        f"Code: <code>{code}</code>\n"
        f"Type: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price', 0)}\n"
        f"Share: {'YES' if data.get('is_share') else 'NO'}\n"
        f"User: @{user.username or 'hidden'}"
    )

    await call.answer()
