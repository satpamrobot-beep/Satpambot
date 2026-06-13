import re

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


# =========================
# MENU GET MEDIA
# =========================
@router.callback_query(F.data == "getmedia")
async def getmedia_menu(callback: CallbackQuery):

    await callback.message.edit_text(
        "📥 GET MEDIA\n\n"
        "Kirim kode:\n\n"
        "/get earnfilebot_xxxxx"
    )

    await callback.answer()


# =========================
# SAFE GET MEDIA
# =========================
@router.message(F.text.regexp(r"^/get"))
async def get_media(message: Message):

    text = (message.text or "").strip()

    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return await message.answer("❌ Contoh:\n/get earnfilebot_xxxxx")

    code = parts[1].strip()

    # validasi format code
    if not re.fullmatch(r"earnfilebot_[A-Za-z0-9]+", code):
        return await message.answer("❌ Format code tidak valid")

    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM uploads WHERE code=$1",
                code
            )

    except Exception as e:
        print("DB ERROR:", e)
        return await message.answer("❌ Database error")

    if not row:
        return await message.answer("❌ Code tidak ditemukan")

    photos = row["photos"] or []
    videos = row["videos"] or []

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
        f"""📦 FILE FOUND

🔑 CODE : {code}
📸 PHOTO : {len(photos)}
🎥 VIDEO : {len(videos)}
📦 TOTAL : {len(photos)+len(videos)}
💰 MODE : {row['mode']}""",
        reply_markup=kb
    )


# =========================
# OPEN FILE (FIXED + ANTI ERROR)
# =========================
@router.callback_query(F.data.startswith("openfile:"))
async def open_file(callback: CallbackQuery):

    code = callback.data.split(":", 1)[1]

    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM uploads WHERE code=$1",
                code
            )

    except Exception as e:
        print("OPEN DB ERROR:", e)
        return await callback.answer("❌ Database error", show_alert=True)

    if not row:
        return await callback.answer("❌ File tidak ditemukan", show_alert=True)

    photos = row["photos"] or []
    videos = row["videos"] or []

    # =========================
    # FILTER VALID FILE_ID
    # =========================
    def valid_file_id(x):
        return isinstance(x, str) and len(x) > 10

    photos = [p for p in photos if valid_file_id(p)]
    videos = [v for v in videos if valid_file_id(v)]

    if not photos and not videos:
        return await callback.answer("❌ Media rusak / kosong", show_alert=True)

    media = []

    for photo in photos:
        media.append(InputMediaPhoto(media=photo))

    for video in videos:
        media.append(InputMediaVideo(media=video))

    # =========================
    # SEND SAFE BATCH
    # =========================
    try:
        while media:
            chunk = media[:10]
            media = media[10:]

            await callback.message.answer_media_group(media=chunk)

    except Exception as e:
        print("MEDIA ERROR:", e)
        return await callback.answer(
            "❌ File ada yang rusak (file_id invalid)",
            show_alert=True
        )

    await callback.answer("✅ File berhasil dibuka")
