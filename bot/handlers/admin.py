from aiogram import Router, F
from aiogram.types import Message

router = Router()

ADMIN_IDS = [6847035364]  # ganti dengan ID kamu


@router.message(F.text.startswith("/admin"))
async def admin_panel(message: Message):
    user_id = message.from_user.id

    # 🔒 security check
    if user_id not in ADMIN_IDS:
        await message.answer("❌ Not allowed")
        return

    text = (
        "🛠 <b>ADMIN PANEL</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Status: Active\n"
        "Access granted ✔️"
    )

    await message.answer(text)
