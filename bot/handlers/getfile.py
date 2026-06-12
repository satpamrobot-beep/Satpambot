import json

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject

from db.pool import DB  # asumsi kamu pakai async DB (Supabase/Postgres)

router = Router()


# =========================
# START + GETFILE
# =========================
@router.message(CommandStart(deep_link=True))
async def start(message: Message, command: CommandObject):
    user = message.from_user
    payload = command.args

    # =========================
    # NORMAL START
    # =========================
    if not payload:
        return await message.answer("📌 Dashboard bot kamu di sini")

    # =========================
    # GETFILE MODE
    # =========================
    code = payload.replace("decodefilebot_", "")

    # =========================
    # AMBIL DATA DARI DATABASE
    # =========================
    row = await DB.fetchrow(
        "SELECT * FROM uploads WHERE code = $1",
        code
    )

    # =========================
    # FILE TIDAK DITEMUKAN
    # =========================
    if not row:
        return await message.answer(
            "❌ FILE TIDAK DITEMUKAN\n\n"
            f"🔑 CODE: {code}"
        )

    # =========================
    # PARSE MEDIA
    # =========================
    media = row["media"]

    if isinstance(media, str):
        media = json.loads(media)

    # =========================
    # INFO FILE
    # =========================
    await message.answer(
        "📥 FILE FOUND\n\n"
        f"🔑 CODE: {code}\n"
        f"💰 TYPE: {'PAID' if row['is_paid'] else 'FREE'}\n"
        f"💵 PRICE: {row['price']}\n"
        f"🌍 SHARE: {'PUBLIC' if row['is_public'] else 'PRIVATE'}\n"
        f"📦 TOTAL: {len(media)} FILES\n\n"
        "📤 SENDING FILE..."
    )

    # =========================
    # KIRIM MEDIA
    # =========================
    for item in media:
        try:
            mtype = item[0]
            file_id = item[1]

            if mtype == "photo":
                await message.answer_photo(file_id)

            elif mtype == "video":
                await message.answer_video(file_id)

            elif mtype == "doc":
                await message.answer_document(file_id)

        except Exception:
            continue
