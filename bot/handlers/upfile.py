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
# SESSION (LEVEL 3 SAFE STRUCT)
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
    tag = []
    if p: tag.append(f"{p}p")
    if v: tag.append(f"{v}v")
    if d: tag.append(f"{d}d")
    return "_".join(tag)


# =========================
# START UPLOAD
# =========================
@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    if uid in SESSION and SESSION[uid].get("active"):
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
        "📤 <b>UPLOAD MODE</b>\n\n"
        "📎 Kirim media (foto/video/dokumen)\n"
        "⚡ Klik DONE kalau selesai",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ DONE", callback_data="up_done")],
            [InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")]
        ])
    )

    await call.answer()


# =========================
# RECEIVE MEDIA (LEVEL 3 ANTI FLOOD STABLE)
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

    # INIT MESSAGE
    if not sess["msg"]:
        sess["msg"] = await message.answer(f"📦 Media terkumpul: <b>{total}</b>")
        sess["count"] = total
        sess["last"] = now
        return

    # ANTI SPAM UPDATE
    if total == sess["count"]:
        return

    if now - sess["last"] < 0.7:
        return

    try:
        await sess["msg"].edit_text(f"📦 Media terkumpul: <b>{total}</b>")
        sess["count"] = total
        sess["last"] = now
    except:
        pass


# =========================
# DONE
# =========================
@router.callback_query(F.data == "up_done")
async def done(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess or not sess["media"]:
        return await call.answer("❌ Tidak ada media", show_alert=True)

    if sess["lock"]:
        return await call.answer("⏳ Processing...", show_alert=True)

    sess["lock"] = True
    sess["done"] = True

    media = sess["media"]

    p = sum(1 for x in media if x[0] == "photo")
    v = sum(1 for x in media if x[0] == "video")
    d = sum(1 for x in media if x[0] == "doc")

    await state.update_data(
        media=media,
        photo=p,
        video=v,
        doc=d
    )

    await state.set_state(UploadState.choose_type)

    await call.message.edit_text(
        f"📊 TOTAL MEDIA: <b>{len(media)}</b>\n\nPilih tipe:",
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
# CANCEL
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id

    SESSION.pop(uid, None)
    await state.clear()

    await call.answer("❌ Cancelled", show_alert=True)

    await call.message.edit_text("🏠 Kembali ke menu")


# =========================
# TYPE
# =========================
@router.callback_query(F.data.in_({"type_free", "type_paid"}))
async def type_handler(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    if data.get("lock"):
        return await call.answer("⏳", show_alert=True)

    await state.update_data(lock=True)

    is_paid = call.data == "type_paid"
    await state.update_data(is_paid=is_paid)

    if is_paid:
        await state.set_state(UploadState.price)
        await call.message.edit_text("💰 Masukkan harga (1000 - 50000)")
    else:
        await state.update_data(price=0)
        await state.set_state(UploadState.share)

        await call.message.edit_text(
            "🔗 SHARE MODE",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton("🌍 PUBLIC", callback_data="share_yes"),
                    InlineKeyboardButton("🔒 PRIVATE", callback_data="share_no")
                ]
            ])
        )

    await call.answer()


# =========================
# PRICE
# =========================
@router.message(UploadState.price)
async def price_handler(message: Message, state: FSMContext):

    if not message.text.isdigit():
        return await message.answer("❌ angka saja")

    price = int(message.text)

    if price < 1000 or price > 50000:
        return await message.answer("❌ 1000 - 50000")

    await state.update_data(price=price)
    await state.set_state(UploadState.share)

    await message.answer(
        "🔗 SHARE MODE",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton("🌍 PUBLIC", callback_data="share_yes"),
                InlineKeyboardButton("🔒 PRIVATE", callback_data="share_no")
            ]
        ])
    )


# =========================
# SHARE
# =========================
@router.callback_query(F.data.in_({"share_yes", "share_no"}))
async def share_handler(call: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    is_share = call.data == "share_yes"
    await state.update_data(share=is_share)

    await state.set_state(UploadState.review)

    await call.message.edit_text(
        "📋 <b>REVIEW</b>\n\n"
        f"📦 Media: {len(data.get('media', []))}\n"
        f"💰 Type : {'PAID' if data.get('is_paid') else 'FREE'}\n"
        f"💵 Price: {data.get('price', 0)}\n"
        f"🔗 Share: {'YES' if is_share else 'NO'}\n\n"
        "Klik SAVE",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("💾 SAVE", callback_data="save_upload")]
        ])
    )

    await call.answer()


# =========================
# SAVE (LEVEL 3 FINAL CLEAN UI)
# =========================
@router.callback_query(F.data == "save_upload")
async def save(call: CallbackQuery, state: FSMContext):

    uid = call.from_user.id
    user = call.from_user
    data = await state.get_data()

    media = data.get("media", [])

    p = data.get("photo", 0)
    v = data.get("video", 0)
    d = data.get("doc", 0)

    code = f"earnfilebot_{rand(14)}_{build_media_tag(p,v,d)}"

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
        code, uid, user.username,
        media, p, v, d,
        data.get("is_paid", False),
        data.get("price", 0),
        data.get("share", False)
        )

    SESSION.pop(uid, None)
    await state.clear()

    is_paid = data.get("is_paid")
    price = data.get("price", 0)
    share = data.get("share")

    price_text = f"💵 : {price}" if is_paid else ""
    share_text = "🔓 Share" if share else "🔒 Private"

    await call.message.edit_text(
f"""🎉 MEDIA SUCCESS SAVED

🔑 Code : {code}
📦 Total : {len(media)} media
Type  : {'PAID' if is_paid else 'FREE'}
{price_text}
{share_text}
Create By @{user.username or 'hidden'}"""
    )

    await call.answer()
