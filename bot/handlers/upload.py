import json
import secrets
import string
import time

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.db.database import get_pool

router = Router()

SESSIONS = {}

CHANNEL_ID = -1003721009353

def normalize_list(data):
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except:
            return []
    return []
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
        "processing": False,
        "saving": False,
    }


# =========================
# KEYBOARD
# =========================
def upload_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ DONE",
                    callback_data="up_done"
                ),
                InlineKeyboardButton(
                    text="❌ CANCEL",
                    callback_data="up_cancel"
                ),
            ]
        ]
    )


def mode_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆓 FREE",
                    callback_data="up_free"
                ),
                InlineKeyboardButton(
                    text="💰 PAYMENT",
                    callback_data="up_pay"
                ),
            ]
        ]
    )


def share_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔓 SHARE",
                    callback_data="up_share"
                ),
                InlineKeyboardButton(
                    text="🔒 NO SHARE",
                    callback_data="up_noshare"
                ),
            ]
        ]
    )


def save_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💾 SAVE",
                    callback_data="up_save"
                ),
                InlineKeyboardButton(
                    text="❌ CANCEL",
                    callback_data="up_cancel"
                ),
            ]
        ]
    )
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

    if not s:
        return

    if s.get("finished"):
        return

    # SAVE MEDIA
    if message.photo:

        file_id = message.photo[-1].file_id

        if file_id not in s["photos"]:
            s["photos"].append(file_id)

    elif message.video:

        file_id = message.video.file_id

        if file_id not in s["videos"]:
            s["videos"].append(file_id)

    photo_count = len(s["photos"])
    video_count = len(s["videos"])
    total = photo_count + video_count

    # DELETE USER MESSAGE
    try:
        await message.delete()
    except Exception:
        pass

    # UPDATE UI MAX 4x/DETIK
    now = time.time()

    if now - s.get("last_update", 0) < 0.25:
        return

    s["last_update"] = now

    msg_id = s.get("msg_id")
    chat_id = s.get("chat_id")

    if not msg_id or not chat_id:
        return

    try:
        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=(
                "📥 RECEIVED\n\n"
                f"📸 Photo : {photo_count}\n"
                f"🎥 Video : {video_count}\n"
                f"📦 Total : {total}\n\n"
                "Tekan DONE jika selesai upload."
            ),
            reply_markup=upload_kb()
        )

    except Exception:
        pass
# =========================
# DONE
# =========================
@router.callback_query(F.data == "up_done")
async def done(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer(
            "Session expired",
            show_alert=True
        )

    # anti spam click
    if s.get("finished"):
        return await callback.answer()

    total = len(s["photos"]) + len(s["videos"])

    if total == 0:
        return await callback.answer(
            "Upload media terlebih dahulu",
            show_alert=True
        )

    s["finished"] = True

    try:
        await callback.message.edit_text(
            "⚙️ PILIH MODE\n\n"
            f"📸 Photo : {len(s['photos'])}\n"
            f"🎥 Video : {len(s['videos'])}\n"
            f"📦 Total : {total}\n\n"
            "Pilih metode file:",
            reply_markup=mode_kb()
        )
    except Exception:
        pass

    await callback.answer()
# =========================
# FREE / PAY / SHARE (UNCHANGED CORE)
# =========================
@router.callback_query(F.data == "up_free")
async def free(callback: CallbackQuery):

    uid = callback.from_user.id
    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer(
            "Session expired",
            show_alert=True
        )

    if s.get("saving"):
        return await callback.answer()

    s["mode"] = "free"
    s["payment"] = 0

    try:
        await callback.message.edit_text(
            "🔓 PILIH SHARE TYPE\n\n"
            "Pilih apakah file dapat dibagikan ulang atau tidak.",
            reply_markup=share_kb()
        )
    except Exception:
        pass

    await callback.answer()

@router.message(UploadState.payment_input)
async def payment_input(message: Message, state: FSMContext):

    uid = message.from_user.id
    s = SESSIONS.get(uid)

    if not s:
        return

    text = (message.text or "").strip()

    if not text.isdigit():
        return await message.answer(
            "❌ Nominal harus berupa angka"
        )

    amount = int(text)

    if amount < 1:
        return await message.answer(
            "❌ Nominal minimal Rp 1"
        )

    s["payment"] = amount

    try:
        await message.delete()
    except:
        pass

    await state.clear()

    if s.get("chat_id") and s.get("msg_id"):
        try:
            await message.bot.edit_message_text(
                chat_id=s["chat_id"],
                message_id=s["msg_id"],
                text=(
                    "🔓 PILIH SHARE TYPE\n\n"
                    f"💰 Harga: Rp {amount:,}"
                ),
                reply_markup=share_kb()
            )
        except:
            pass


@router.callback_query(F.data == "up_pay")
async def pay(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer(
            "Session expired",
            show_alert=True
        )

    if s.get("saving"):
        return await callback.answer()

    s["mode"] = "payment"
    s["payment"] = 0

    await state.set_state(
        UploadState.payment_input
    )

    await callback.message.edit_text(
        "💰 INPUT NOMINAL\n\n"
        "Masukkan harga file dalam angka.\n"
        "Contoh: 5000"
    )

    await callback.answer()


@router.callback_query(F.data == "up_share")
async def share(callback: CallbackQuery):

    uid = callback.from_user.id
    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer(
            "Session expired",
            show_alert=True
        )

    s["share"] = "share"

    await callback.message.edit_text(
        "💾 READY SAVE\n\n"
        "🔓 Share : Diizinkan",
        reply_markup=save_kb()
    )

    await callback.answer()

@router.callback_query(F.data == "up_noshare")
async def noshare(callback: CallbackQuery):

    uid = callback.from_user.id
    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer(
            "Session expired",
            show_alert=True
        )

    s["share"] = "no_share"

    await callback.message.edit_text(
        "💾 READY SAVE\n\n"
        "🔒 Share : Tidak Diizinkan",
        reply_markup=save_kb()
    )

    await callback.answer()
# =========================
# SAVE (SAFE + CLEAN)
# =========================
@router.callback_query(F.data == "up_save")
async def save(callback: CallbackQuery, state: FSMContext):

    uid = callback.from_user.id
    user = callback.from_user

    s = SESSIONS.get(uid)

    if not s:
        return await callback.answer(
            "❌ Session expired",
            show_alert=True
        )

    # Anti spam save
    if s.get("saving"):
        return await callback.answer(
            "⏳ Sedang menyimpan...",
            show_alert=True
        )

    s["saving"] = True

    try:

        # =========================
        # VALIDATION
        # =========================

        if not s.get("mode"):
            return await callback.answer(
                "❌ Pilih mode terlebih dahulu",
                show_alert=True
            )

        if not s.get("share"):
            return await callback.answer(
                "❌ Pilih share type terlebih dahulu",
                show_alert=True
            )

        photo_count = len(s["photos"])
        video_count = len(s["videos"])
        total = photo_count + video_count

        if total == 0:
            return await callback.answer(
                "❌ Media kosong",
                show_alert=True
            )

        if (
            s["mode"] == "payment"
            and s["payment"] <= 0
        ):
            return await callback.answer(
                "❌ Nominal belum diisi",
                show_alert=True
            )

        # =========================
        # FORMAT TEXT
        # =========================

        price_text = (
            "FREE"
            if s["mode"] == "free"
            else f"Rp {s['payment']:,}"
        )

        share_text = (
            "SHARE"
            if s["share"] == "share"
            else "NO SHARE"
        )

        username = (
            f"@{user.username}"
            if user.username
            else user.full_name
        )

        code = generate_code()

        # =========================
        # SAVE DATABASE
        # =========================

        pool = get_pool()

        try:

            async with pool.acquire() as conn:

                await conn.execute(
                    """
                    INSERT INTO uploads (
                        user_id,
                        code,
                        photos,
                        videos,
                        mode,
                        payment,
                        share_type,
                        created_at
                    )
                    VALUES (
                        $1,
                        $2,
                        $3::jsonb,
                        $4::jsonb,
                        $5,
                        $6,
                        $7,
                        NOW()
                    )
                    """,
                    uid,
                    code,
                    s["photos"]),
                    s["videos"]),
                    s["mode"],
                    s["payment"],
                    s["share"]
                )

        except Exception as e:

            print("DB ERROR:", e)

            return await callback.answer(
                "❌ Database error",
                show_alert=True
            )

        # =========================
        # MARKETPLACE POST
        # =========================

        try:

            await callback.bot.send_message(
                chat_id=CHANNEL_ID,
                text=(
                    "📦 <b>NEW MARKET ITEM</b>\n"
                    "━━━━━━━━━━━━━━\n\n"
                    f"🔑 Code: <code>{code}</code>\n"
                    f"👤 Creator: {username}\n"
                    f"📸 Photos: {photo_count}\n"
                    f"🎥 Videos: {video_count}\n"
                    f"💰 Price: {price_text}\n"
                    f"🔐 Share: {share_text}\n\n"
                    f"📅 Created: {time.strftime('%d/%m/%Y %H:%M')}\n"
                    "━━━━━━━━━━━━━━"
                ),
                parse_mode="HTML"
            )

        except Exception as e:
            print("POST ERROR:", e)

        # =========================
        # CLEAR SESSION
        # =========================

        SESSIONS.pop(uid, None)

        await state.clear()

        try:

            await callback.message.edit_text(
                "🎉 SUCCESS SAVE\n\n"
                f"🔑 CODE : {code}\n"
                f"📸 PHOTO : {photo_count}\n"
                f"🎥 VIDEO : {video_count}\n"
                f"💰 PRICE : {price_text}\n"
                f"🔐 SHARE : {share_text}\n\n"
                "📤 Posted to marketplace"
            )

        except Exception:
            pass

        await callback.answer(
            "✅ Berhasil disimpan"
        )

    finally:

        session = SESSIONS.get(uid)

        if session:
            session["saving"] = False
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
