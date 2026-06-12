import asyncio
import time
import re
import secrets
import string
from db.pool import DB

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

# ================= CONFIG =================

MAX_MEDIA = 100
MAX_FILE_SIZE = 50 * 1024 * 1024

SESSION = {}
LOCKS = {}
USED = set()

# ================= STATE =================

class UploadState(StatesGroup):
    collecting = State()
    choose_type = State()
    price = State()
    share = State()
    review = State()

# ================= UTIL =================

def gen_code():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))

# ================= KEYBOARD =================

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
        [InlineKeyboardButton(text="✏️ Edit Type", callback_data="edit_type")],
        [InlineKeyboardButton(text="📁 Add Media", callback_data="edit_media")],
        [InlineKeyboardButton(text="🌍 Edit Share", callback_data="edit_share")]
    ])

# ================= START =================

@router.callback_query(F.data == "upfile")
async def start(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id

    SESSION[uid] = {
        "media": [],
        "done": False,
        "msg": None,
        "created": time.time()
    }

    await state.set_state(UploadState.collecting)

    msg = await call.message.edit_text(
        "📁 Upload Mode\n\n0/100\nKirim media...",
        reply_markup=kb_upload()
    )

    SESSION[uid]["msg"] = msg
    await call.answer()

# ================= RECEIVE =================

@router.message(UploadState.collecting)
async def receive(message: Message, state: FSMContext):
    if not (message.photo or message.video or message.document):
        return

    uid = message.from_user.id
    lock = LOCKS.setdefault(uid, asyncio.Lock())

    async with lock:
        sess = SESSION.get(uid)
        if not sess or sess["done"]:
            return

        if len(sess["media"]) >= MAX_MEDIA:
            return

        if message.photo:
            f = message.photo[-1]
            sess["media"].append(("photo", f.file_id, f.file_size or 0))
        elif message.video:
            sess["media"].append(("video", message.video.file_id, message.video.file_size or 0))
        elif message.document:
            sess["media"].append(("doc", message.document.file_id, message.document.file_size or 0))

        try:
            await message.delete()
        except:
            pass

        total = len(sess["media"])

        try:
            await sess["msg"].edit_text(
                f"📁 Upload Mode\n\n{total}/{MAX_MEDIA}",
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
        return await call.answer("Belum ada media", True)

    sess["done"] = True

    await state.update_data(media=sess["media"])
    await state.set_state(UploadState.choose_type)

    await call.message.edit_text("Pilih tipe:", reply_markup=kb_type())
    await call.answer()

# ================= CANCEL =================

@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    SESSION.pop(call.from_user.id, None)
    await state.clear()

    await call.message.edit_text("❌ Cancel\nKetik /start")
    await call.answer()

# ================= TYPE =================

@router.callback_query(F.data.in_(["free", "paid"]))
async def tipe(call: CallbackQuery, state: FSMContext):
    is_paid = call.data == "paid"

    await state.update_data(is_paid=is_paid)

    if is_paid:
        await state.set_state(UploadState.price)
        await call.message.edit_text("Masukkan harga (minimal 10000):")
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
        return await message.answer("Format salah, contoh: 10000")

    price_val = int(txt)

    if price_val < 10000:
        return await message.answer("Minimal 10000")

    await state.update_data(price=price_val)
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
        f"Price: {data.get('price')}\n"
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
    link = f"https://t.me/Decodefilebot?start={code}"

    # 🔥 SIMPAN KE DATABASE
    try:
        await DB.execute("""
            INSERT INTO uploads (code, user_id, is_paid, price, is_public, media)
            VALUES ($1,$2,$3,$4,$5,$6)
        """,
            code,
            call.from_user.id,
            data.get("is_paid"),
            data.get("price"),
            data.get("public"),
            data.get("media")
        )
    except Exception as e:
        return await call.message.edit_text(f"❌ DB ERROR\n{e}")

    # 🔥 TAMPILKAN INFO LENGKAP (GABUNGAN)
    await call.message.edit_text(
        f"✅ SUCCESS\n\n"
        f"Code: {code}\n"
        f"Link: {link}\n"
        f"Type: {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price')}\n"
        f"Share: {'PUBLIC' if data.get('public') else 'PRIVATE'}\n"
        f"Total Media: {len(data.get('media', []))}"
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
    await call.message.edit_text("Tambah media lagi:", reply_markup=kb_upload())
    await call.answer()

@router.message(F.text.startswith("/pay"))
async def pay(message: Message):

    args = message.text.split()

    if len(args) < 2:
        return await message.answer("Format: /pay CODE")

    code = args[1]

    row = await DB.fetchrow("SELECT * FROM uploads WHERE code=$1", code)

    if not row:
        return await message.answer("Code tidak valid")

    if not row["is_paid"]:
        return await message.answer("Ini gratis")

    await message.answer(
        f"💰 Bayar dulu\nHarga: {row['price']}"
    )

from aiogram.types import InputMediaPhoto, InputMediaVideo, FSInputFile

async def send_media(message: Message, media):
    group = []

    for m in media:
        tipe, file_id, _ = m

        if tipe == "photo":
            group.append(InputMediaPhoto(media=file_id))
        elif tipe == "video":
            group.append(InputMediaVideo(media=file_id))
        elif tipe == "doc":
            # doc gak bisa digroup → kirim satu-satu
            await message.answer_document(file_id)
            continue

        if len(group) == 10:
            await message.answer_media_group(group)
            group = []

    if group:
        await message.answer_media_group(group)


@router.message(F.text.startswith("/start"))
async def start_cmd(message: Message):
    args = message.text.split()

    if len(args) < 2:
        return await message.answer("Welcome")

    code = args[1]

    row = await DB.fetchrow("SELECT * FROM uploads WHERE code=$1", code)

    if not row:
        return await message.answer("Code tidak valid")

    # 🔒 BARU CEK USED SETELAH VALID
    if code in USED:
        return await message.answer("Link sudah digunakan")

    if row["is_paid"]:
        return await message.answer(
            f"💰 Konten berbayar\nHarga: {row['price']}\n\nKetik /pay {code}"
        )

    # ✅ TANDAI
    USED.add(code)

    await send_media(message, row["media"])
