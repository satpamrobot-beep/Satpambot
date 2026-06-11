from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

ADMIN_IDS = [6847035364]


def is_admin(user_id: int):
    return user_id in ADMIN_IDS


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Maintenance", callback_data="adm_maintenance")],
        [InlineKeyboardButton(text="📊 Stats", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="💳 Withdraw", callback_data="adm_withdraw")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_home")]
    ])


@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Not allowed", show_alert=True)

    await call.message.edit_text(
        "👑 <b>ADMIN DASHBOARD</b>\n━━━━━━━━━━━━━━",
        reply_markup=admin_kb()
    )
    await call.answer()
