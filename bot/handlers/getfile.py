import json
from aiogram import Router, F
from aiogram.types import Message, InputMediaPhoto, InputMediaVideo
from db.pool import DB

router = Router()


# ================= SEND MEDIA =================
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
            await message.answer_media_group(group)
            group = []

    if group:
        await message.answer_media_group(group)


# ================= GET FILE (PAKAI CODE TEXT) =================
@router.message(F.text)
async def getfile_by_code(message: Message):
    text = message.text.strip()

    # ❌ skip command lain
    if text.startswith("/"):
        return

    code = text.upper()

    # ambil DB
    row = await DB.fetchrow("""
        SELECT code, media, is_paid, price, is_public, protect
        FROM uploads
        WHERE code=$1
    """, code)

    if not row:
        return  # diam saja biar gak spam “code tidak valid”

    # 💰 paid file
    if row["is_paid"]:
        return await message.answer(
            f"💰 FILE BERBAYAR\n\n"
            f"Price: {row['price']}\n\n"
            f"Ketik:\n/pay {code}"
        )

    # 🔥 parse media
    try:
        media = json.loads(row["media"])
    except:
        return await message.answer("❌ File rusak")

    protect = row["protect"]

    await send_media(
        message,
        media,
        protect=protect
    )
