from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.admin import admin_dashboard_kb

router = Router()

ADMIN_IDS = [6847035364]  # ganti sesuai ID kamu


# =========================
# CHECK ADMIN
# =========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================
# OPEN ADMIN DASHBOARD
# =========================
@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    user_id = call.from_user.id

    # ⚡ admin validation
    if not is_admin(user_id):
        await call.answer("❌ Not allowed", show_alert=True)
        return

    text = (
        "👑 <b>ADMIN DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Welcome Admin Control Panel\n"
        "━━━━━━━━━━━━━━\n"
        "Pilih menu di bawah 👇"
    )

    try:
        await call.message.edit_text(
            text,
            reply_markup=admin_dashboard_kb()
        )
    except:
        # fallback kalau edit gagal (misalnya message lama)
        await call.message.answer(
            text,
            reply_markup=admin_dashboard_kb()
        )

    await call.answer()
