import secrets
import string

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.db.database import get_pool

router = Router()

SESSIONS = {}

CHANNEL_ID = -1001234567890  # ganti ke group/channel kamu
# =========================
# STATE
# =========================
class UploadState(StatesGroup):
    collecting = State()
    payment_input = State()


# =========================
# SESSION
# =========================
def new_session():
    return {
        "photos": 0,
        "videos": 0,
        "mode": None,
        "payment": 0,
        "share": None,
    }


# =========================
# KEYBOARD
# =========================
def upload_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ DONE", callback_data="up_done"),
            InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")
        ]
    ])


def mode_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆓 FREE", callback_data="up_free"),
            InlineKeyboardButton(text="💰 PAYMENT", callback_data="up_pay")
        ]
    ])


def share_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔓 SHARE", callback_data="up_share"),
            InlineKeyboardButton(text="🔒 NO SHARE", callback_data="up_noshare")
        ]
    ])


def save_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 SAVE", callback_data="up_save"),
            InlineKeyboardButton(text="❌ CANCEL", callback_data="up_cancel")
        ]
    ])


# =========================
# CODE
# =========================
def generate_code():
    rand = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    return f"earnfilebot_{rand}"


# =========================
# START
# =========================
@router.callback_query(F.data == "upmedia")
async def start_upload(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    SESSIONS[uid] = new_session()

    await state.set_state(UploadState.collecting)

    await callback.message.edit_text(
        "📤 UPLOAD MODE ACTIVE\nKirim photo / video sekarang",
        reply_markup=upload_kb()
    )

    await callback.answer()


# =========================
# COLLECT MEDIA
# =========================
@router.message(UploadState.collecting, F.photo | F.video)
async def collect_media(message: Message):

    uid = message.from_user.id
    if uid not in SESSIONS:
        return

    s = SESSIONS[uid]

    if message.photo:
        s["photos"] += 1
    else:
        s["videos"] += 1

    total = s["photos"] + s["videos"]

    await message.answer(
        f"📥 RECEIVED\n"
        f"📸 Photo: {s['photos']}\n"
        f"🎥 Video: {s['videos']}\n"
        f"📦 Total: {total}"
    )


# =========================
# DONE → MODE
# =========================
@router.callback_query(F.data == "up_done")
async def done(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    if uid not in SESSIONS:
        return await callback.answer("Session expired", show_alert=True)

    await state.set_state(None)

    await callback.message.edit_text(
        "⚙️ PILIH MODE",
        reply_markup=mode_kb()
    )

    await callback.answer()


# =========================
# FREE MODE
# =========================
@router.callback_query(F.data == "up_free")
async def free(callback: CallbackQuery):

    uid = callback.from_user.id
    SESSIONS[uid]["mode"] = "free"

    await callback.message.edit_text(
        "🔓 SHARE TYPE",
        reply_markup=share_kb()
    )

    await callback.answer()


# =========================
# PAYMENT MODE
# =========================
@router.callback_query(F.data == "up_pay")
async def pay(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    SESSIONS[uid]["mode"] = "payment"

    await state.set_state(UploadState.payment_input)

    await callback.message.edit_text(
        "💰 INPUT NOMINAL (contoh: 10000)"
    )

    await callback.answer()


# =========================
# PAYMENT INPUT
# =========================
@router.message(UploadState.payment_input)
async def set_payment(message: Message):

    uid = message.from_user.id
    if uid not in SESSIONS:
        return

    value = message.text.replace(".", "").replace(",", "")

    if not value.isdigit():
        return await message.answer("❌ Angka tidak valid")

    SESSIONS[uid]["payment"] = int(value)

    await message.answer(
        "🔓 PILIH SHARE TYPE",
        reply_markup=share_kb()
    )


# =========================
# SHARE
# =========================
@router.callback_query(F.data == "up_share")
async def share(callback: CallbackQuery):

    uid = callback.from_user.id
    SESSIONS[uid]["share"] = "share"

    await callback.message.edit_text("💾 READY SAVE", reply_markup=save_kb())
    await callback.answer()


@router.callback_query(F.data == "up_noshare")
async def noshare(callback: CallbackQuery):

    uid = callback.from_user.id
    SESSIONS[uid]["share"] = "no_share"

    await callback.message.edit_text("💾 READY SAVE", reply_markup=save_kb())
    await callback.answer()


# =========================
# SAVE
# =========================
@router.callback_query(F.data == "up_save")
async def save(callback: CallbackQuery):

    uid = callback.from_user.id
    user = callback.from_user

    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer("Session expired", show_alert=True)

    code = generate_code()

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO uploads (
                user_id, code, photos, videos, mode, payment, share_type
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        uid, code,
        s["photos"], s["videos"],
        s["mode"], s["payment"], s["share"]
        )

    # =========================
    # CREATOR NAME
    # =========================
    username = f"@{user.username}" if user.username else user.full_name

    # =========================
    # FORMAT MESSAGE
    # =========================
    post_text = (
        "📦 <b>NEW UPLOAD</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔑 Code: <code>{code}</code>\n"
        f"📸 Photo: {s['photos']}\n"
        f"🎥 Video: {s['videos']}\n"
        f"💰 Payment: {s['payment']}\n"
        f"🔐 Share: {s['share']}\n\n"
        f"👤 Created by: {username}\n"
        "━━━━━━━━━━━━━━"
    )

    # =========================
    # AUTO POST TO GROUP
    # =========================
    try:
        await callback.bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
            parse_mode="HTML"
        )
    except Exception as e:
        print("POST ERROR:", e)

    # =========================
    # USER RESPONSE
    # =========================
    await callback.message.edit_text(
        f"✅ SUCCESS\n\n"
        f"CODE: {code}\n"
        f"📸 Photo: {s['photos']}\n"
        f"🎥 Video: {s['videos']}\n"
        f"💰 Payment: {s['payment']}\n"
        f"🔐 Share: {s['share']}\n\n"
        f"📤 Posted to group"
    )

    SESSIONS.pop(uid, None)
    await callback.answer()

@router.callback_query(F.data == "up_cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):

    SESSIONS.pop(callback.from_user.id, None)
    await state.clear()

    await callback.answer("Cancelled", show_alert=False)

    await callback.message.edit_text("❌ CANCELLED / BACK TO HOME")
