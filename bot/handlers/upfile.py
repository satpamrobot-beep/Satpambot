import asyncio
import re
import secrets
import string
import json

from db.pool import DB

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

# ================= CONFIG =================

MAX_MEDIA = 100

SESSION = {}

# ================= STATE =================

class UploadState(StatesGroup):
    collecting = State()
    choose_type = State()
    price = State()
    share = State()
    review = State()

# ================= UTIL =================

def gen_code():
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    return f"decodefilebot_{code}"

def gen_link(code: str):
    # FIX UTAMA: format telegram benar
    return f"https://t.me/decodefilebot?start={code}"

# ================= KEYBOARD (AIROGRAM V3 FIX) =================

def kb_upload():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Done", callback_data="done")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])

def kb_type():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 Free", callback_data="free")],
        [InlineKeyboardButton(text="💰 Paid", callback_data="paid")]
    ])

def kb_share():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Public", callback_data="pub")],
        [InlineKeyboardButton(text="🔒 Private", callback_data="pri")]
    ])

def kb_review():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Save", callback_data="save")],
        [InlineKeyboardButton(text="✏️ Type", callback_data="edit_type")],
        [InlineKeyboardButton(text="💰 Price", callback_data="edit_price")],
        [InlineKeyboardButton(text="📁 Media", callback_data="edit_media")],
        [InlineKeyboardButton(text="🌍 Share", callback_data="edit_share")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
    ])

# ================= START =================

@router.callback_query(F.data == "upfile")
async def start(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    SESSION[uid] = {
        "media": [],
        "is_paid": False,
        "price": 0,
        "public": True
    }

    await state.set_state(UploadState.collecting)

    await call.message.edit_text(
        "📁 Upload Mode\n\nKirim media...",
        reply_markup=kb_upload()
    )

    await call.answer()

# ================= RECEIVE MEDIA =================

@router.message(UploadState.collecting)
async def receive(message: Message, state: FSMContext):

    uid = message.from_user.id
    sess = SESSION.get(uid)

    if not sess:
        return

    if len(sess["media"]) >= MAX_MEDIA:
        return

    if message.photo:
        f = message.photo[-1]
        sess["media"].append(("photo", f.file_id))

    elif message.video:
        sess["media"].append(("video", message.video.file_id))

    elif message.document:
        sess["media"].append(("doc", message.document.file_id))

    try:
        await message.delete()
    except:
        pass

# ================= DONE =================

@router.callback_query(F.data == "done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess or not sess["media"]:
        return await call.answer("Belum ada media", show_alert=True)

    await state.update_data(media=sess["media"])
    await state.set_state(UploadState.choose_type)

    await call.message.edit_text(
        "Pilih tipe:",
        reply_markup=kb_type()
    )

    await call.answer()

# ================= TYPE =================

@router.callback_query(F.data.in_(["free", "paid"]))
async def choose_type(call: CallbackQuery, state: FSMContext):

    is_paid = call.data == "paid"
    await state.update_data(is_paid=is_paid)

    if is_paid:
        await state.set_state(UploadState.price)
        await call.message.edit_text("Masukkan harga:")
    else:
        await state.update_data(price=0)
        await state.set_state(UploadState.share)
        await call.message.edit_text("Pilih share:", reply_markup=kb_share())

    await call.answer()

# ================= PRICE =================

@router.message(UploadState.price)
async def price(message: Message, state: FSMContext):

    txt = re.sub(r"\D", "", message.text or "")

    if not txt:
        return await message.answer("Format salah")

    await state.update_data(price=int(txt))
    await state.set_state(UploadState.share)

    await message.answer("Pilih share:", reply_markup=kb_share())

# ================= SHARE =================

@router.callback_query(F.data.in_(["pub", "pri"]))
async def share(call: CallbackQuery, state: FSMContext):

    is_pub = call.data == "pub"
    await state.update_data(public=is_pub)

    data = await state.get_data()

    await state.set_state(UploadState.review)

    await call.message.edit_text(
        f"📋 REVIEW\n\n"
        f"Type: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price', 0)}\n"
        f"Share: {'PUBLIC' if is_pub else 'PRIVATE'}\n"
        f"Media: {len(data.get('media', []))}",
        reply_markup=kb_review()
    )

    await call.answer()

# ================= SAVE =================

@router.callback_query(F.data == "save")
async def save(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    code = gen_code()
    link = gen_link(code)

    await DB.execute("""
        INSERT INTO uploads(code, user_id, is_paid, price, is_public, media)
        VALUES ($1,$2,$3,$4,$5,$6)
    """,
        code,
        call.from_user.id,
        data.get("is_paid"),
        data.get("price"),
        data.get("public"),
        json.dumps(data.get("media", []))
    )

    await call.message.edit_text(
        f"✅ SUCCESS\n\n"
        f"CODE: {code}\n"
        f"LINK: {link}\n"
        f"TYPE: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"PRICE: {data.get('price')}\n"
        f"MEDIA: {len(data.get('media', []))}"
    )

    SESSION.pop(call.from_user.id, None)
    await state.clear()
    await call.answer()

# ================= EDIT =================

@router.callback_query(F.data == "edit_type")
async def edit_type(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.choose_type)
    await call.message.edit_text("Pilih tipe:", reply_markup=kb_type())
    await call.answer()

@router.callback_query(F.data == "edit_share")
async def edit_share(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.share)
    await call.message.edit_text("Pilih share:", reply_markup=kb_share())
    await call.answer()

@router.callback_query(F.data == "edit_media")
async def edit_media(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.collecting)
    await call.message.edit_text("Tambah media...")
    await call.answer()

@router.callback_query(F.data == "edit_price")
async def edit_price(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.price)
    await call.message.edit_text("Masukkan harga:")
    await call.answer()

# ================= CANCEL =================

@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    SESSION.pop(call.from_user.id, None)
    await state.clear()

    await call.message.edit_text("❌ Cancelled")
    await call.answer()
