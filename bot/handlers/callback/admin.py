from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.admin import admin_dashboard_kb

router = Router()

ADMIN_IDS = {6847035364}  # pakai set biar lebih cepat & aman


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

    # ⚡ ADMIN CHECK
    if user_id not in ADMIN_IDS:
        return await call.answer("❌ Not allowed", show_alert=True)

    text = (
        "👑 <b>ADMIN DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Welcome Admin Control Panel\n"
        "━━━━━━━━━━━━━━\n"
        "Pilih menu di bawah 👇"
    )

    # =========================
    # SAFE EDIT (ANTI ERROR)
    # =========================
    try:
        await call.message.edit_text(
            text,
            reply_markup=admin_dashboard_kb()
        )
    except Exception:
        # kalau message tidak bisa diedit → fallback
        await call.message.answer(
            text,
            reply_markup=admin_dashboard_kb()
        )

    await call.answer()
