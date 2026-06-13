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
# HELPER
# =========================
def is_valid_file_id(x: str) -> bool:
    return isinstance(x, str) and len(x) > 10


# =========================
# MENU
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
# GET MEDIA (FIXED + ANTI DIAM)
# =========================
@router.message(F.text.startswith("/get"))
async def get_media(message: Message):

    print("GET HANDLER TRIGGERED")  # DEBUG WAJIB

    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        return await message.answer("❌ Contoh:\n/get earnfilebot_xxxxx")

    code = parts[1].strip()

    if not code.startswith("earnfilebot_"):
        return await message.answer("❌ Format code salah")

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
# OPEN FILE (AUTO REPAIR SAFE)
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

    photos = normalize_list(row["photos"])
    videos = normalize_list(row["videos"])

    clean_photos = [x for x in photos if isinstance(x, str) and len(x) > 20]
    clean_videos = [x for x in videos if isinstance(x, str) and len(x) > 20]

    if not clean_photos and not clean_videos:
        return await callback.answer("❌ Media kosong / rusak", show_alert=True)

    media = [
        InputMediaPhoto(m) for m in clean_photos
    ] + [
        InputMediaVideo(m) for m in clean_videos
    ]

    try:
        for i in range(0, len(media), 10):
            await callback.message.answer_media_group(media=media[i:i+10])

    except Exception as e:
        print("MEDIA ERROR:", e)
        return await callback.answer("❌ File rusak", show_alert=True)

    await callback.answer("✅ File berhasil dibuka")
