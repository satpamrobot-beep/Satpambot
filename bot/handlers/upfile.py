import asyncio
import string
import random
import time
import json

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
UPLOAD_LOCKS = {}
SESSION = {}

MAX_MEDIA = 100
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024


class UploadState(StatesGroup):
    collecting = State()
    choose_type = State()
    price = State()
    share = State()
    review = State()


def rand(n=14):
    return ''.join(
        random.choices(
            string.ascii_letters + string.digits,
            k=n
        )
    )


def build_media_tag(p=0, v=0, d=0):
    parts = []

    if p:
        parts.append(f"{p}p")

    if v:
        parts.append(f"{v}v")

    if d:
        parts.append(f"{d}d")

    return "_".join(parts)


UPLOAD_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ DONE",
                callback_data="up_done"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ CANCEL",
                callback_data="up_cancel"
            )
        ]
    ]
)


def kb_type():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆓 FREE",
                    callback_data="type_free"
                ),
                InlineKeyboardButton(
                    text="💰 PAID",
                    callback_data="type_paid"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ CANCEL",
                    callback_data="up_cancel"
                )
            ]
        ]
    )


def kb_visibility():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 PUBLIC",
                    callback_data="share_yes"
                ),
                InlineKeyboardButton(
                    text="🔒 PRIVATE",
                    callback_data="share_no"
                )
            ]
        ]
    )


def kb_save():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💾 SAVE TO CLOUD",
                    callback_data="save_upload"
                )
            ]
        ]
    )


# =========================
# START
# =========================

@router.callback_query(F.data == "upfile")
async def upfile(
    call: CallbackQuery,
    state: FSMContext
):

    uid = call.from_user.id

    if SESSION.get(uid, {}).get("active"):
        return await call.answer(
            "⛔ Masih ada sesi upload aktif",
            show_alert=True
        )

    SESSION[uid] = {
        "active": True,
        "media": [],
        "msg": None,
        "last": 0,
        "done": False,
        "lock": False,
        "created": time.time()
    }

    await state.set_state(
        UploadState.collecting
    )

    try:

        msg = await call.message.edit_text(
            (
                "📁 <b>UPLOAD MODE</b>\n\n"
                "📦 Total     : 0/100\n"
                "🖼 Photo     : 0\n"
                "🎥 Video     : 0\n"
                "📄 Document  : 0\n\n"
                "👇 Kirim file kamu"
            ),
            reply_markup=UPLOAD_KB,
            parse_mode="HTML"
        )

        SESSION[uid]["msg"] = msg or call.message

    except Exception as e:

        print(
            f"UPLOAD PANEL ERROR: {e}"
        )

    await call.answer()
# =========================
# RECEIVE
# =========================

@router.message(
    UploadState.collecting,
    F.photo | F.video | F.document
)
async def receive(
    message: Message,
    state: FSMContext
):

    uid = message.from_user.id

    lock = UPLOAD_LOCKS.setdefault(
        uid,
        asyncio.Lock()
    )

    async with lock:

        sess = SESSION.get(uid)

        if not sess:
            return

        if sess.get("done"):
            return

        if len(sess["media"]) >= MAX_MEDIA:

            try:
                await message.delete()
            except:
                pass

            return

        # =========================
        # PHOTO
        # =========================

        if message.photo:

            sess["media"].append(
                (
                    "photo",
                    message.photo[-1].file_id
                )
            )

        # =========================
        # VIDEO
        # =========================

        elif message.video:

            if (
                message.video.file_size
                and
                message.video.file_size > MAX_FILE_SIZE
            ):
                return

            sess["media"].append(
                (
                    "video",
                    message.video.file_id
                )
            )

        # =========================
        # DOCUMENT
        # =========================

        elif message.document:

            if (
                message.document.file_size
                and
                message.document.file_size > MAX_FILE_SIZE
            ):
                return

            sess["media"].append(
                (
                    "doc",
                    message.document.file_id
                )
            )

        # =========================
        # COUNTER
        # =========================

        photo_count = sum(
            1 for x in sess["media"]
            if x[0] == "photo"
        )

        video_count = sum(
            1 for x in sess["media"]
            if x[0] == "video"
        )

        doc_count = sum(
            1 for x in sess["media"]
            if x[0] == "doc"
        )

        total = len(sess["media"])

        # =========================
        # HAPUS PESAN USER
        # =========================

        try:
            await message.delete()
        except:
            pass

        # =========================
        # UPDATE PANEL
        # =========================

        try:

            panel = sess.get("msg")

            if panel:

                await panel.edit_text(
                    (
                        "📁 <b>UPLOAD MODE</b>\n\n"
                        f"📦 Total     : {total}/{MAX_MEDIA}\n"
                        f"🖼 Photo     : {photo_count}\n"
                        f"🎥 Video     : {video_count}\n"
                        f"📄 Document  : {doc_count}\n\n"
                        "👇 Klik DONE jika selesai"
                    ),
                    reply_markup=UPLOAD_KB,
                    parse_mode="HTML"
                )

        except Exception as e:

            print(
                "UPLOAD PANEL ERROR:",
                e
            )
# =========================
# DONE
# =========================

@router.callback_query(F.data == "up_done")
async def done(
    call: CallbackQuery,
    state: FSMContext
):

    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess:
        return await call.answer()

    if sess.get("lock"):
        return await call.answer()

    sess["lock"] = True

    try:

        if not sess["media"]:
            return await call.answer(
                "❌ kosong",
                show_alert=True
            )

        media = list(sess["media"])

        p = sum(
            1
            for x in media
            if x[0] == "photo"
        )

        v = sum(
            1
            for x in media
            if x[0] == "video"
        )

        d = sum(
            1
            for x in media
            if x[0] == "doc"
        )

        sess["done"] = True

        await state.update_data(
            media=media,
            photo=p,
            video=v,
            doc=d
        )

        await state.set_state(
            UploadState.choose_type
        )

        try:
            await call.message.edit_text(
                f"☁️ UPLOAD DONE\n\nTotal: {len(media)}",
                reply_markup=kb_type()
            )
        except:
            pass

    finally:
        sess["lock"] = False

    await call.answer()


# =========================
# TYPE
# =========================

@router.callback_query(
    F.data.in_(
        {
            "type_free",
            "type_paid"
        }
    )
)
async def type_handler(
    call: CallbackQuery,
    state: FSMContext
):

    is_paid = (
        call.data == "type_paid"
    )

    await state.update_data(
        is_paid=is_paid
    )

    if is_paid:

        await state.set_state(
            UploadState.price
        )

        await call.message.edit_text(
            "💰 Masukkan harga"
        )

    else:

        await state.update_data(
            price=0
        )

        await state.set_state(
            UploadState.share
        )

        await call.message.edit_text(
            "Visibility",
            reply_markup=kb_visibility()
        )

    await call.answer()


# =========================
# PRICE
# =========================

@router.message(
    UploadState.price
)
async def price_handler(
    message: Message,
    state: FSMContext
):

    if (
        not message.text
        or
        not message.text.isdigit()
    ):
        return await message.answer(
            "❌ Masukkan angka"
        )

    price = int(message.text)

    if price <= 0:
        return await message.answer(
            "❌ Harga minimal 1"
        )

    await state.update_data(
        price=price
    )

    await state.set_state(
        UploadState.share
    )

    await message.answer(
        "Visibility",
        reply_markup=kb_visibility()
    )


# =========================
# SHARE
# =========================

@router.callback_query(
    F.data.in_(
        {
            "share_yes",
            "share_no"
        }
    )
)
async def share_handler(
    call: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    await state.update_data(
        share=(
            call.data == "share_yes"
        )
    )

    await state.set_state(
        UploadState.review
    )

    await call.message.edit_text(
        f"REVIEW\nFiles: {len(data.get('media', []))}",
        reply_markup=kb_save()
    )

    await call.answer()


# =========================
# SAVE
# =========================

@router.callback_query(F.data == "save_upload")
async def save(
    call: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()
    media = data.get("media", [])

    user = call.from_user

    username = user.username

    display_name = (
        f"@{username}"
        if username
        else user.full_name
    )

    tag = build_media_tag(
        data.get("photo", 0),
        data.get("video", 0),
        data.get("doc", 0)
    )

    code = f"earnfilebot_{rand(14)}_{tag}"

    try:

        pool = get_pool()

        async with pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO uploads (
                    code,
                    user_id,
                    username,
                    media,
                    photo_count,
                    video_count,
                    doc_count,
                    is_paid,
                    price,
                    is_share,
                    created_at
                )
                VALUES (
                    $1,$2,$3,$4,
                    $5,$6,$7,
                    $8,$9,$10,
                    NOW()
                )
                """,
                code,
                user.id,
                username or user.full_name,
                json.dumps(media),
                data.get("photo", 0),
                data.get("video", 0),
                data.get("doc", 0),
                data.get("is_paid", False),
                data.get("price", 0),
                data.get("share", False)
            )

    except Exception as e:

        SESSION.pop(
            user.id,
            None
        )

        await state.clear()

        return await call.message.edit_text(
            f"❌ DB ERROR\n\n{e}"
        )

    SESSION.pop(
        user.id,
        None
    )

    await state.clear()

    await call.message.edit_text(
        f"""🎉 SUCCESS SAVE

🔑 CODE:
<code>{code}</code>

📦 FILE:
{len(media)}

👤 CREATE BY:
{display_name}
"""
    )

    await call.answer()


# =========================
# CANCEL
# =========================

@router.callback_query(F.data == "up_cancel")
async def cancel_upload(
    call: CallbackQuery,
    state: FSMContext
):

    SESSION.pop(
        call.from_user.id,
        None
    )

    await state.clear()

    try:
        await call.message.edit_text(
            "❌ Upload dibatalkan"
        )
    except:
        pass

    await call.answer()
