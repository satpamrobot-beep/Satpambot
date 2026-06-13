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
# GET CODE (FIXED SAFE VERSION)
# =========================
import re

@router.message(F.text)
async def get_media(message: Message):

    text = (message.text or "").strip()

    # cari code di mana saja dalam pesan
    match = re.search(r"earnfilebot_[A-Za-z0-9]+", text)

    if not match:
        return  # jangan spam reply (biar gak ganggu chat lain)

    code = match.group(0)

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
# OPEN FILE
# =========================
@router.callback_query(F.data.startswith("openfile:"))
async def open_file(callback: CallbackQuery):

    code = callback.data.split(":", 1)[1]

    pool = get_pool()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM uploads
                WHERE code=$1
                """,
                code
            )

    except Exception as e:
        print("OPEN DB ERROR:", e)
        return await callback.answer("❌ Database error", show_alert=True)

    if not row:
        return await callback.answer(
            "❌ File tidak ditemukan",
            show_alert=True
        )

    photos = row["photos"] or []
    videos = row["videos"] or []

    media = []

    for photo in photos:
        media.append(InputMediaPhoto(media=photo))

    for video in videos:
        media.append(InputMediaVideo(media=video))

    if not media:
        return await callback.answer(
            "❌ Media kosong",
            show_alert=True
        )

    while media:
        chunk = media[:10]
        media = media[10:]

        await callback.message.answer_media_group(media=chunk)

    await callback.answer("✅ File berhasil dibuka")
