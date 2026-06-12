from aiogram import Router, F
from aiogram.types import Message
from db.pool import DB

router = Router()

# ================= SEND MEDIA =================

from aiogram.types import InputMediaPhoto, InputMediaVideo

async def send_media(message: Message, media, protect: bool = False):
    group = []

    for m in media:
        tipe, file_id, _ = m

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

        if len(group) == 10:
            await message.answer_media_group(
                group,
                protect_content=protect
            )
            group = []

    if group:
        await message.answer_media_group(
            group,
            protect_content=protect
        )


# ================= GET FILE =================

@router.message(F.text.startswith("/start"))
async def get_file(message: Message):
    args = message.text.split()

    # 🔹 kalau cuma /start
    if len(args) < 2:
        return await message.answer("👋 Welcome")

    code = args[1]

    # 🔥 AMBIL DATA DARI DB
    row = await DB.fetchrow("""
        SELECT code, media, is_paid, price, is_public, protect
        FROM uploads
        WHERE code=$1
    """, code)

    if not row:
        return await message.answer("❌ File tidak ditemukan")

    # 💰 PAID FILE
    if row["is_paid"]:
        return await message.answer(
            f"💰 FILE BERBAYAR\n\n"
            f"Price: {row['price']}\n\n"
            f"Ketik:\n/pay {code}"
        )

    # 🔥 CEK MEDIA
    if not row["media"]:
        return await message.answer("❌ File kosong")

    # 🔐 PROTECT LOGIC
    protect = row["protect"]  # True = PRIVATE, False = PUBLIC

    # 🚀 KIRIM FILE
    await send_media(
        message,
        row["media"],
        protect=protect
    )
