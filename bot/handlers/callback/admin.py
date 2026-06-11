from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.admin import admin_dashboard_kb

router = Router()

ADMIN_IDS = [6847035364]  # ganti ke ID kamu


def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# =========================
# OPEN ADMIN DASHBOARD
# =========================
@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Not allowed", show_alert=True)

    text = (
        "👑 <b>ADMIN DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Welcome Admin Panel Control System\n"
        "Pilih menu di bawah 👇"
    )

    await call.message.edit_text(text, reply_markup=admin_dashboard_kb())
    await call.answer()
