import json

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    InputMediaVideo
)

from bot.db.database import get_pool

router = Router()

@router.callback_query(F.data == "getmedia")
async def getmedia_menu(callback: CallbackQuery):

    await callback.message.edit_text(
        "📥 GET MEDIA\n\n"
        "Kirim kode:\n\n"
        "/get earnfilebot_xxxxx"
    )

    await callback.answer()


# =========================
# GET CODE
# =========================
@router.message(F.text.startswith("/get "))
async def get_media(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        return await message.answer(
            "❌ Contoh:\n/get earnfilebot_xxxxx"
        )

    code = parts[1].strip()

    pool = get_pool()

    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT *
            FROM uploads
            WHERE code=$1
            """,
            code
        )

    if not row:
        return await message.answer(
            "❌ Code tidak ditemukan"
        )

    photos = row["photos"] or []
    videos = row["videos"] or []

    photo_count = len(photos)
    video_count = len(videos)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 OPEN FILE",
                    callback_data=f"openfile:{code}"
                )
            ]
        ]
    )

    await message.answer(
        (
            "📦 FILE FOUND\n\n"
            f"🔑 CODE : {code}\n"
            f"📸 PHOTO : {photo_count}\n"
            f"🎥 VIDEO : {video_count}\n"
            f"📦 TOTAL : {photo_count + video_count}\n\n"
            f"💰 MODE : {row['mode']}"
        ),
        reply_markup=kb
    )


# =========================
# OPEN FILE
# =========================
@router.callback_query(F.data.startswith("openfile:"))
async def open_file(callback: CallbackQuery):

    code = callback.data.split(":", 1)[1]

    pool = get_pool()

    async with pool.acquire() as conn:

        row = await conn.fetchrow(
            """
            SELECT *
            FROM uploads
            WHERE code=$1
            """,
            code
        )

    if not row:
        return await callback.answer(
            "❌ File tidak ditemukan",
            show_alert=True
        )

    photos = row["photos"] or []
    videos = row["videos"] or []

    media = []

    for photo in photos:
        media.append(
            InputMediaPhoto(
                media=photo
            )
        )

    for video in videos:
        media.append(
            InputMediaVideo(
                media=video
            )
        )

    if not media:
        return await callback.answer(
            "❌ Media kosong",
            show_alert=True
        )

    while media:

        chunk = media[:10]
        media = media[10:]

        await callback.message.answer_media_group(
            media=chunk
        )

    await callback.answer(
        "✅ File berhasil dibuka"
    )
