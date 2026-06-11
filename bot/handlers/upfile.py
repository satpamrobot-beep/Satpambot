import asyncio
import string
import random
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.pool import get_pool

router = Router()

# =========================
# SESSION CLEAN
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
# UTIL
# =========================
def rand(n=14):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

def build_media_tag(p=0, v=0, d=0):
    parts = []
    if p: parts.append(f"{p}p")
    if v: parts.append(f"{v}v")
    if d: parts.append(f"{d}d")
    return "_".join(parts)

# =========================
# KEYBOARD (STICK UI)
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

    if SESSION.get(uid, {}).get("active"):
        return await call.answer("⛔ Upload masih berjalan", show_alert=True)

    SESSION[uid] = {
        "active": True,
        "media": [],
        "msg": None,
        "last": 0,
        "count": 0,
        "done": False,
        "lock": False
    }

    await state.set_state(UploadState.collecting)

    await call.message.edit_text(
        "📁 <b>Google Drive Upload</b>\n\n"
        "📎 Kirim file (foto / video / dokumen)\n"
        "⚡ Klik DONE kalau selesai",
        reply_markup=UPLOAD_KB
    )

    await call.answer()

# =========================
# RECEIVE MEDIA
# =========================
@router.message(UploadState.collecting, F.content_type.in_({"photo", "video", "document"}))
async def receive(message: Message, state: FSMContext):

    uid = message.from_user.id
    sess = SESSION.get(uid)

    if not sess or sess.get("done"):
        return

    if message.photo:
        sess["media"].append(("photo", message.photo[-1].file_id))
    elif message.video:
        sess["media"].append(("video", message.video.file_id))
    else:
        sess["media"].append(("doc", message.document.file_id))

    total = len(sess["media"])
    now = time.time()

    if not sess["msg"]:
        sess["msg"] = await message.answer(
            f"📦 Uploading...\nFiles: {total}",
            reply_markup=UPLOAD_KB
        )
        sess["count"] = total
        sess["last"] = now
        return

    if total == sess["count"]:
        return

    if now - sess["last"] < 0.8:
        return

    try:
        await sess["msg"].edit_text(
            f"📦 Uploading...\nFiles: {total}",
            reply_markup=UPLOAD_KB
        )
        sess["count"] = total
        sess["last"] = now
    except:
        pass

# =========================
# DONE (CLEAR RAM + NEXT STEP)
# =========================
@router.callback_query(F.data == "up_done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess or not sess["media"]:
        return await call.answer("❌ Tidak ada file", show_alert=True)

    if sess["lock"]:
        return await call.answer("⏳ Processing...", show_alert=True)

    sess["lock"] = True
    sess["done"] = True

    media = sess["media"]

    p = sum(1 for x in media if x[0] == "photo")
    v = sum(1 for x in media if x[0] == "video")
    d = sum(1 for x in media if x[0] == "doc")

    # AUTO CLEAR RAM
    sess["media"].clear()

    await state.update_data(media=media, photo=p, video=v, doc=d)
    await state.set_state(UploadState.choose_type)

    await call.message.edit_text(
        "☁️ <b>Upload Complete</b>\n\n"
        f"📦 Total: {len(media)}\n"
        f"🖼 {p} | 🎥 {v} | 📄 {d}\n\n"
        "Pilih tipe:",
        reply_markup=kb_type()
    )

    await call.answer()

# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    SESSION.pop(uid, None)
    await state.clear()

    await call.answer("❌ Cancelled", show_alert=True)
    await call.message.edit_text("🏠 Dashboard")

# =========================
# TYPE
# =========================
@router.callback_query(F.data.in_({"type_free", "type_paid"}))
async def type_handler(call: CallbackQuery, state: FSMContext):

    is_paid = call.data == "type_paid"
    await state.update_data(is_paid=is_paid)

    if is_paid:
        await state.set_state(UploadState.price)
        await call.message.edit_text("💰 Masukkan harga (1000 - 50000)")
    else:
        await state.update_data(price=0)
        await state.set_state(UploadState.share)
        await call.message.edit_text("🔗 Visibility", reply_markup=kb_visibility())

    await call.answer()

# =========================
# PRICE
# =========================
@router.message(UploadState.price)
async def price_handler(message: Message, state: FSMContext):

    if not message.text or not message.text.isdigit():
        return await message.answer("❌ angka saja")

    price = int(message.text)

    if price < 1000 or price > 50000:
        return await message.answer("❌ 1000 - 50000")

    await state.update_data(price=price)
    await state.set_state(UploadState.share)

    await message.answer("🔗 Visibility", reply_markup=kb_visibility())

# =========================
# SHARE
# =========================
@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share_handler(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    await state.update_data(share=(call.data == "share_yes"))
    await state.set_state(UploadState.review)

    await call.message.edit_text(
        "📋 <b>Review</b>\n\n"
        f"Files: {len(data.get('media', []))}\n"
        f"Type : {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price', 0)}\n"
        f"Share: {call.data.replace('share_', '').upper()}\n",
        reply_markup=kb_save()
    )

    await call.answer()

# =========================
# SAVE
# =========================
@router.callback_query(F.data == "save_upload")
async def save(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    media = data.get("media", [])

    code = f"earnfilebot_{rand(14)}_{build_media_tag(data.get('photo',0), data.get('video',0), data.get('doc',0))}"

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
        call.from_user.id,
        call.from_user.username,
        media,
        data.get("photo",0),
        data.get("video",0),
        data.get("doc",0),
        data.get("is_paid", False),
        data.get("price", 0),
        data.get("share", False)
        )

    SESSION.pop(call.from_user.id, None)
    await state.clear()

    await call.message.edit_text(
        f"""🎉 SUCCESS SAVE

🔑 CODE: <code>{code}</code>
📦 FILE: {len(media)}
💰 TYPE: {'PAID' if data.get('is_paid') else 'FREE'}"""
    )

    await call.answer()
