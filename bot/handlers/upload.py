import secrets
import string
import time

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.db.database import get_pool

router = Router()

SESSIONS = {}

CHANNEL_ID = -1003721009353


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
        "photos": [],
        "videos": [],
        "mode": None,
        "payment": 0,
        "share": None,
        "msg_id": None,
        "chat_id": None,
        "finished": False,
        "last_update": 0,
        "processing": False,  # 🔥 simple lock (lebih aman dari asyncio.Lock di dict)
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

    msg = await callback.message.edit_text(
        "📤 UPLOAD MODE ACTIVE\n\nKirim photo / video sekarang",
        reply_markup=upload_kb()
    )

    SESSIONS[uid]["msg_id"] = msg.message_id
    SESSIONS[uid]["chat_id"] = msg.chat.id

    await callback.answer()


# =========================
# COLLECT MEDIA (STABLE)
# =========================
@router.message(UploadState.collecting, F.photo | F.video)
async def collect_media(message: Message):

    uid = message.from_user.id
    s = SESSIONS.get(uid)

    if not s or s["finished"]:
        return

    # 🔥 ANTI PARALLEL EXECUTION
    if s["processing"]:
        return

    s["processing"] = True

    try:
        now = time.time()

        # 🔥 anti spam update
        if now - s["last_update"] < 0.25:
            return
        s["last_update"] = now

        # SAVE MEDIA
        if message.photo:
            file_id = message.photo[-1].file_id
            if file_id not in s["photos"]:
                s["photos"].append(file_id)

        elif message.video:
            file_id = message.video.file_id
            if file_id not in s["videos"]:
                s["videos"].append(file_id)

        total = len(s["photos"]) + len(s["videos"])

        # delete user message
        try:
            await message.delete()
        except:
            pass

        text = (
            "📥 RECEIVED\n"
            f"📸 Photo: {len(s['photos'])}\n"
            f"🎥 Video: {len(s['videos'])}\n"
            f"📦 Total: {total}"
        )

        if s.get("msg_id") and s.get("chat_id"):
            try:
                await message.bot.edit_message_text(
                    chat_id=s["chat_id"],
                    message_id=s["msg_id"],
                    text=text,
                    reply_markup=upload_kb()
                )
            except:
                pass

    finally:
        s["processing"] = False


# =========================
# DONE
# =========================
@router.callback_query(F.data == "up_done")
async def done(callback: CallbackQuery, state: FSMContext):

    s = SESSIONS.get(callback.from_user.id)
    if not s:
        return await callback.answer("Session expired", show_alert=True)

    s["finished"] = True
    await state.set_state(UploadState.payment_input)

    await callback.message.edit_text(
        "⚙️ PILIH MODE",
        reply_markup=mode_kb()
    )

    await callback.answer()


# =========================
# FREE / PAY / SHARE (UNCHANGED CORE)
# =========================
@router.callback_query(F.data == "up_free")
async def free(callback: CallbackQuery):
    SESSIONS[callback.from_user.id]["mode"] = "free"
    await callback.message.edit_text("🔓 SHARE TYPE", reply_markup=share_kb())
    await callback.answer()


@router.callback_query(F.data == "up_pay")
async def pay(callback: CallbackQuery, state: FSMContext):
    SESSIONS[callback.from_user.id]["mode"] = "payment"
    await state.set_state(UploadState.payment_input)
    await callback.message.edit_text("💰 INPUT NOMINAL")
    await callback.answer()


@router.callback_query(F.data == "up_share")
async def share(callback: CallbackQuery):
    SESSIONS[callback.from_user.id]["share"] = "share"
    await callback.message.edit_text("💾 READY SAVE", reply_markup=save_kb())
    await callback.answer()


@router.callback_query(F.data == "up_noshare")
async def noshare(callback: CallbackQuery):
    SESSIONS[callback.from_user.id]["share"] = "no_share"
    await callback.message.edit_text("💾 READY SAVE", reply_markup=save_kb())
    await callback.answer()


# =========================
# SAVE (SAFE + CLEAN)
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
                user_id, code,
                photos, videos,
                mode, payment, share_type
            )
            VALUES ($1,$2,$3,$4,$5,$6,$7)
        """,
        uid, code,
        s["photos"],
        s["videos"],
        s["mode"],
        s["payment"],
        s["share"]
        )

    username = f"@{user.username}" if user.username else user.full_name

    post_text = (
        "📦 <b>NEW MARKET ITEM</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🔑 Code: <code>{code}</code>\n"
        f"👤 Creator: {username}\n"
        f"📸 Photos: {len(s['photos'])}\n"
        f"🎥 Videos: {len(s['videos'])}\n"
        f"💰 Price: {s['payment']}\n"
        f"🔐 Share: {s['share']}\n"
        "━━━━━━━━━━━━━━"
    )

    try:
        await callback.bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
            parse_mode="HTML"
        )
    except Exception as e:
        print("POST ERROR:", e)

    SESSIONS.pop(uid, None)

    await callback.message.edit_text(
        f"✅ SUCCESS\n\nCODE: {code}\n📤 Posted to marketplace"
    )

    await callback.answer()


# =========================
# CANCEL
# =========================
@router.callback_query(F.data == "up_cancel")
async def cancel(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    SESSIONS.pop(uid, None)
    await state.clear()

    await callback.answer("❌ Cancelled", show_alert=True)
    await callback.message.edit_text("🏠 Back to home")
