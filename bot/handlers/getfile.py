import json
from aiogram import Router, F
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo

from db.pool import DB

router = Router()

# ================= SEND MEDIA =================

async def send_media(message: Message, media, protect: bool = False):
    group = []

    for m in media:
        try:
            tipe, file_id, _ = m
        except:
            continue

        if tipe == "photo":
            group.append(InputMediaPhoto(media=file_id))

        elif tipe == "video":
            group.append(InputMediaVideo(media=file_id))

        elif tipe == "doc":
            await message.answer_document(
                file_id,
                protect_content=protect
            )
            continue

        # kirim batch max 10
        if len(group) == 10:
            try:
                await message.answer_media_group(group)
            except:
                pass
            group = []

    if group:
        try:
            await message.answer_media_group(group)
        except:
            pass


# ================= GET FILE =================

@router.message(F.text.startswith("/start"))
async def get_file(message: Message):
    args = message.text.split()

    # /start biasa
    if len(args) < 2:
        return await message.answer("👋 Welcome")

    code = args[1]

    # ================= AMBIL DATA =================
    row = await DB.fetchrow("""
        SELECT code, media, is_paid, price, is_public, protect
        FROM uploads
        WHERE code=$1
    """, code)

    if not row:
        return await message.answer("❌ Code tidak ditemukan")

    # ================= PAID SYSTEM =================
    if row["is_paid"]:
        return await message.answer(
            f"💰 FILE BERBAYAR\n\n"
            f"Price: {row['price']}\n\n"
            f"Ketik:\n/pay {code}"
        )

    # ================= CEK MEDIA =================
    if not row["media"]:
        return await message.answer("❌ File kosong")

    # ================= DECODE MEDIA (FIX PENTING) =================
    try:
        media = json.loads(row["media"])
    except:
        media = row["media"]

    if not isinstance(media, list):
        return await message.answer("❌ Format media rusak")

    # ================= PROTECT MODE =================
    protect = bool(row["protect"])

    # ================= SEND MEDIA =================
    await send_media(
        message=message,
        media=media,
        protect=protect
    )
