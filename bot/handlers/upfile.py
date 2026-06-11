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
# SESSION CLEAN (NO NUMPUK)
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
# UI BUTTON (ALWAYS STICK)
# =========================
UPLOAD_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ DONE", callback_data="up_done")],
    [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
])


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
# START UPLOAD (DRIVE UI)
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
        "⚡ Semua file akan tersimpan sementara\n\n"
        "Tekan DONE jika selesai upload",
        reply_markup=UPLOAD_KB
    )

    await call.answer()


# =========================
# RECEIVE MEDIA (DRIVE STYLE CLEAN)
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

    # FIRST UI MESSAGE (LIKE DRIVE)
    if not sess["msg"]:
        sess["msg"] = await message.answer(
            f"📦 <b>Uploading...</b>\n"
            f"Files: {total}\n\n"
            "Status: syncing to cloud...",
            reply_markup=UPLOAD_KB
        )
        sess["count"] = total
        sess["last"] = now
        return

    # NO SPAM UPDATE
    if total == sess["count"]:
        return

    if now - sess["last"] < 0.8:
        return

    try:
        await sess["msg"].edit_text(
            f"📦 <b>Uploading to Drive...</b>\n"
            f"Files: {total}\n\n"
            "Status: syncing...",
            reply_markup=UPLOAD_KB
        )
        sess["count"] = total
        sess["last"] = now
    except:
        pass


# =========================
# DONE (AUTO CLEAN MEMORY + UI STEP)
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

    # AUTO CLEAR MEDIA RAM (IMPORTANT)
    sess["media"] = []

    await state.update_data(media=media, photo=p, video=v, doc=d)
    await state.set_state(UploadState.choose_type)

    await call.message.edit_text(
        "☁️ <b>Google Drive Upload Complete</b>\n\n"
        f"📦 Total Files: <b>{len(media)}</b>\n"
        f"🖼 Photos: {p}\n"
        f"🎥 Videos: {v}\n"
        f"📄 Docs: {d}\n\n"
        "Pilih tipe penyimpanan:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🆓 FREE", callback_data="type_free"),
                InlineKeyboardButton(text="💰 PAID", callback_data="type_paid")
            ],
            [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
        ])
    )

    await call.answer()


# =========================
# CANCEL (FULL RESET CLEAN)
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    SESSION.pop(uid, None)
    await state.clear()

    await call.answer("❌ Cancelled", show_alert=True)

    await call.message.edit_text("🏠 Kembali ke Dashboard")


# =========================
# TYPE + PRICE + SHARE + SAVE (tetap simple tapi clean)
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

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
                InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
            ]
        ])

        await call.message.edit_text("🔗 Visibility", reply_markup=kb)

    await call.answer()


@router.message(UploadState.price)
async def price_handler(message: Message, state: FSMContext):

    if not message.text or not message.text.isdigit():
        return await message.answer("❌ angka saja")

    price = int(message.text)

    if price < 1000 or price > 50000:
        return await message.answer("❌ 1000 - 50000")

    await state.update_data(price=price)
    await state.set_state(UploadState.share)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌍 PUBLIC", callback_data="share_yes"),
            InlineKeyboardButton(text="🔒 PRIVATE", callback_data="share_no")
        ]
    ])

    await message.answer("🔗 Visibility", reply_markup=kb)

@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share_handler(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    await state.update_data(share=(call.data == "share_yes"))
    await state.set_state(UploadState.review)

    await call.message.edit_text(
        "📋 <b>Final Review</b>\n\n"
        f"Files: {len(data.get('media', []))}\n"
        f"Type : {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"Price: {data.get('price', 0)}\n"
        f"Share: {call.data.replace('share_', '').upper()}\n\n"
        "Klik SAVE untuk lanjut",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💾 SAVE TO CLOUD", callback_data="save_upload")]
        ])
    )

    await call.answer()
