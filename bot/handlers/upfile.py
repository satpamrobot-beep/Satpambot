import asyncio
import random
import time
import json
import re

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.pool import get_pool

router = Router()

SESSION = {}
UPLOAD_LOCKS = {}

MAX_MEDIA = 100
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
MAX_TOTAL_SIZE = 10 * 1024 * 1024 * 1024  # ✅ FIX


class UploadState(StatesGroup):
    collecting = State()
    choose_type = State()
    price = State()
    share = State()
    review = State()


def rand(n=14):
    return ''.join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=n))


def human_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


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


@router.callback_query(F.data == "upfile")
async def upfile(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    lock = UPLOAD_LOCKS.setdefault(uid, asyncio.Lock())

    if lock.locked():
        return await call.answer()

    async with lock:
        sess = SESSION.get(uid)

        if sess and sess.get("active"):
            return await call.answer("⛔ Masih ada sesi upload aktif", show_alert=True)

        SESSION.pop(uid, None)

        SESSION[uid] = {
            "active": True,
            "media": [],
            "msg": None,
            "done": False,
            "created": time.time(),
            "expire": time.time() + 600
        }

        await state.set_state(UploadState.collecting)

        try:
            msg = await call.message.edit_text(
                f"📁 <b>UPLOAD MODE</b>\n\n📦 Total: 0/{MAX_MEDIA}\n👇 Kirim file kamu",
                reply_markup=UPLOAD_KB,
                parse_mode="HTML"
            )
        except:
            msg = await call.message.answer(
                f"📁 <b>UPLOAD MODE</b>\n\n📦 Total: 0/{MAX_MEDIA}\n👇 Kirim file kamu",
                reply_markup=UPLOAD_KB,
                parse_mode="HTML"
            )

        SESSION[uid]["msg"] = msg
        await call.answer()


@router.message(UploadState.collecting, F.photo | F.video | F.document)
async def receive(message: Message, state: FSMContext):
    uid = message.from_user.id
    lock = UPLOAD_LOCKS.setdefault(uid, asyncio.Lock())

    async with lock:
        sess = SESSION.get(uid)
        if not sess or not sess.get("active"):
            return

        # auto expire
        if time.time() > sess.get("expire", 0):
            SESSION.pop(uid, None)
            return

        if sess.get("done"):
            return

        media_list = sess.setdefault("media", [])

        if len(media_list) >= MAX_MEDIA:
            return

        file_type = None
        file_id = None
        file_size = 0

        if message.photo:
            f = message.photo[-1]
            file_type = "photo"
        elif message.video:
            f = message.video
            file_type = "video"
        else:
            f = message.document
            file_type = "doc"

        file_id = f.file_id
        file_size = f.file_size or 0

        if file_size > MAX_FILE_SIZE:
            return await message.reply("❌ File terlalu besar")

        total_size = sum(x[2] for x in media_list) + file_size
        if total_size > MAX_TOTAL_SIZE:
            return await message.reply("❌ Total size melebihi limit")

        media_list.append((file_type, file_id, file_size))

        p = sum(1 for x in media_list if x[0] == "photo")
        v = sum(1 for x in media_list if x[0] == "video")
        d = sum(1 for x in media_list if x[0] == "doc")

        try:
            await message.delete()
        except:
            pass

        msg = sess.get("msg")
        if msg:
            try:
                await msg.edit_text(
                    f"📁 <b>UPLOAD MODE</b>\n\n"
                    f"📦 Total: {len(media_list)}/{MAX_MEDIA}\n"
                    f"🖼 Photo: {p}\n🎥 Video: {v}\n📄 Doc: {d}\n"
                    f"💾 Size: {human_size(total_size)}",
                    reply_markup=UPLOAD_KB,
                    parse_mode="HTML"
                )
            except:
                pass


@router.callback_query(F.data == "up_done")
async def done(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    sess = SESSION.get(uid)

    if not sess or not sess.get("active"):
        return await call.answer("⚠️ Session tidak valid", show_alert=True)

    media = sess.get("media", [])
    if not media:
        return await call.answer("⚠️ Media kosong", show_alert=True)

    if sess.get("done_locked"):
        return await call.answer()

    sess["done_locked"] = True

    try:
        current = await state.get_state()

        # ✅ FIX STATE
        if current != UploadState.collecting:
            return await call.answer("⚠️ Flow tidak valid", show_alert=True)

        if sess.get("done"):
            return await call.answer("⚠️ Sudah diproses", show_alert=True)

        sess["done"] = True

        photo = sum(1 for m in media if m[0] == "photo")
        video = sum(1 for m in media if m[0] == "video")
        doc = sum(1 for m in media if m[0] == "doc")

        await state.update_data(
            media=media,
            photo=photo,
            video=video,
            doc=doc
        )

        await state.set_state(UploadState.choose_type)

        await call.message.edit_text(
            "☁️ <b>UPLOAD SELESAI</b>\n\n💡 Pilih tipe:",
            reply_markup=kb_type(),
            parse_mode="HTML"
        )

    finally:
        sess["done_locked"] = False

    await call.answer()


@router.callback_query(F.data == "save_upload")
async def save(call: CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    user = call.from_user
    sess = SESSION.get(uid)

    if not sess or sess.get("saved"):
        return await call.answer("⚠️ Sudah disimpan", show_alert=True)

    sess["saved"] = True

    data = await state.get_data()
    code = f"earnfilebot_{rand(14)}"

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO uploads (
                    code,user_id,username,media,
                    photo_count,video_count,doc_count,
                    is_paid,price,is_share,created_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
                """,
                code,
                user.id,
                user.username or user.full_name,
                json.dumps(data.get("media", [])),
                data.get("photo", 0),
                data.get("video", 0),
                data.get("doc", 0),
                data.get("is_paid", False),
                data.get("price", 0),
                data.get("share", False)
            )
    except:
        sess["saved"] = False
        return await call.message.edit_text("❌ Database error")

    await state.clear()
    SESSION.pop(uid, None)
    UPLOAD_LOCKS.pop(uid, None)

    bot_username = (await call.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={code}"

    await call.message.edit_text(
        f"🎉 SUCCESS\n\nCODE:\n{code}\n\nLINK:\n{link}"
    )

    await call.answer()


@router.callback_query(F.data == "up_cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    SESSION.pop(call.from_user.id, None)
    await state.clear()
    await call.message.edit_text("❌ Cancelled")
    await call.answer()
