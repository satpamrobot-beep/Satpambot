import asyncio
import time
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
LOCKS = {}

# ================= STATE =================

class UploadState(StatesGroup):
    collecting = State()
    choose_type = State()
    price = State()
    share = State()
    review = State()
    final = State()

# ================= UTIL =================

def gen_code():
    base = secrets.token_hex(4) + str(time.time())
    return "decodefilebot_" + secrets.token_hex(2) + "_" + base[:10]

def parse_price(text: str) -> int:
    if not text:
        return 0
    text = text.lower().replace(".", "").replace(",", "").replace("k", "000")
    return int(re.sub(r"\D", "", text) or 0)

def make_link(code: str):
    return f"https://t.me/decodefilebot?start={code}"

# ================= KEYBOARD =================

def kb_upload():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ DONE", callback_data="done")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
    ])

def kb_type():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🆓 FREE", callback_data="free")],
        [InlineKeyboardButton("💰 PAY", callback_data="paid")]
    ])

def kb_share():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🌍 SHARE", callback_data="pub")],
        [InlineKeyboardButton("🔒 NO SHARE", callback_data="pri")]
    ])

def kb_review():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💾 SAVE", callback_data="save")],
        [InlineKeyboardButton("✏️ TYPE", callback_data="edit_type")],
        [InlineKeyboardButton("💰 PRICE", callback_data="edit_price")],
        [InlineKeyboardButton("📁 MEDIA", callback_data="edit_media")],
        [InlineKeyboardButton("🌍 SHARE", callback_data="edit_share")],
        [InlineKeyboardButton("❌ CANCEL", callback_data="cancel")]
    ])

# ================= START =================

@router.callback_query(F.data == "upfile")
async def start(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    SESSION[uid] = {
        "media": [],
        "msg_id": None,
        "locked": False
    }

    await state.set_state(UploadState.collecting)

    msg = await call.message.edit_text(
        "📁 UPLOAD MODE\n\nKirim media...",
        reply_markup=kb_upload()
    )

    SESSION[uid]["msg_id"] = msg.message_id
    await call.answer()

# ================= RECEIVE MEDIA =================

@router.message(UploadState.collecting)
async def receive(message: Message, state: FSMContext):

    uid = message.from_user.id
    lock = LOCKS.setdefault(uid, asyncio.Lock())

    async with lock:

        sess = SESSION.get(uid)
        if not sess or sess.get("locked"):
            return

        media = sess["media"]

        if len(media) >= MAX_MEDIA:
            return

        item = None

        if message.photo:
            f = message.photo[-1]
            item = ("photo", f.file_id, f.file_size or 0)

        elif message.video:
            item = ("video", message.video.file_id, message.video.file_size or 0)

        elif message.document:
            item = ("doc", message.document.file_id, message.document.file_size or 0)

        if not item:
            return

        media.append(item)

        await state.update_data(media=media)

        try:
            await message.delete()
        except:
            pass

        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sess["msg_id"],
                text=f"📁 UPLOAD MODE\n\n{len(media)}/{MAX_MEDIA}",
                reply_markup=kb_upload()
            )
        except:
            pass

# ================= DONE =================

@router.callback_query(F.data == "done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess or not sess["media"]:
        return await call.answer("Kosong", True)

    sess["locked"] = True

    await state.update_data(media=sess["media"])
    await state.set_state(UploadState.choose_type)

    await call.message.edit_text(
        "📦 PILIH TIPE:",
        reply_markup=kb_type()
    )

    await call.answer()

# ================= CANCEL =================

@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    SESSION.pop(call.from_user.id, None)
    await state.clear()

    await call.message.edit_text("❌ CANCEL")
    await call.answer()

# ================= TYPE =================

@router.callback_query(F.data.in_(["free", "paid"]))
async def choose_type(call: CallbackQuery, state: FSMContext):

    is_paid = call.data == "paid"

    await state.update_data(is_paid=is_paid)

    if is_paid:
        await state.set_state(UploadState.price)
        await call.message.edit_text("💰 MASUKKAN HARGA:")
    else:
        await state.update_data(price=0)
        await state.set_state(UploadState.share)
        await call.message.edit_text("PILIH SHARE:", reply_markup=kb_share())

    await call.answer()

# ================= PRICE =================

@router.message(UploadState.price)
async def price(message: Message, state: FSMContext):

    price_val = parse_price(message.text)

    if price_val < 10000:
        return await message.answer("Minimal 10000")

    await state.update_data(price=price_val)
    await state.set_state(UploadState.share)

    await message.answer("PILIH SHARE:", reply_markup=kb_share())

# ================= SHARE =================

@router.callback_query(F.data.in_(["pub", "pri"]))
async def share(call: CallbackQuery, state: FSMContext):

    is_public = call.data == "pub"

    await state.update_data(public=is_public)

    data = await state.get_data()

    await state.set_state(UploadState.review)

    await call.message.edit_text(
        f"""📋 REVIEW

Type: {"PAY" if data.get("is_paid") else "FREE"}
Price: {data.get("price")}
Share: {"PUBLIC" if is_public else "NO SHARE"}
Media: {len(data.get("media", []))}
""",
        reply_markup=kb_review()
    )

    await call.answer()

# ================= SAVE FINAL =================

@router.callback_query(F.data == "save")
async def save(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    if uid in LOCKS:
        return await call.answer("Processing...", True)

    LOCKS[uid] = True

    try:
        data = await state.get_data()

        code = gen_code()
        link = make_link(code)

        await DB.execute("""
            INSERT INTO uploads
            (code, user_id, is_paid, price, is_public, media, protect)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
            code,
            uid,
            data.get("is_paid"),
            data.get("price"),
            data.get("public"),
            json.dumps(data.get("media", [])),
            not data.get("public")
        )

        await call.message.edit_text(
            f"""✅ SUCCESS

CODE: {code}
LINK: {link}
TYPE: {"PAY" if data.get("is_paid") else "FREE"}
PRICE: {data.get("price")}
SHARE: {"PUBLIC" if data.get("public") else "NO SHARE"}
MEDIA: {len(data.get("media", []))}
"""
        )

        await state.clear()

    except Exception as e:
        await call.message.edit_text(f"❌ ERROR\n{e}")

    finally:
        LOCKS.pop(uid, None)
        SESSION.pop(uid, None)
        await call.answer()

# ================= EDIT =================

@router.callback_query(F.data == "edit_type")
async def edit_type(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.choose_type)
    await call.message.edit_text("PILIH TIPE:", reply_markup=kb_type())
    await call.answer()

@router.callback_query(F.data == "edit_price")
async def edit_price(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.price)
    await call.message.edit_text("MASUKKAN HARGA:")
    await call.answer()

@router.callback_query(F.data == "edit_share")
async def edit_share(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.share)
    await call.message.edit_text("PILIH SHARE:", reply_markup=kb_share())
    await call.answer()

@router.callback_query(F.data == "edit_media")
async def edit_media(call: CallbackQuery, state: FSMContext):
    await state.set_state(UploadState.collecting)
    await SESSION[call.from_user.id].update({"locked": False})
    await call.message.edit_text("TAMBAH MEDIA:", reply_markup=kb_upload())
    await call.answer()
