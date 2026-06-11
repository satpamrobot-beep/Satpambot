from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

ADMIN_IDS = [6847035364]


def is_admin(user_id: int):
    return user_id in ADMIN_IDS


def admin_dashboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛠 Maintenance", callback_data="adm_maintenance"),
            InlineKeyboardButton(text="💳 Withdraw User", callback_data="adm_withdraw"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistik", callback_data="adm_stats"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="adm_broadcast"),
        ],
        [
            InlineKeyboardButton(text="➕ Add Admin", callback_data="adm_add_admin"),
            InlineKeyboardButton(text="👥 User Online", callback_data="adm_online"),
        ],
        [
            InlineKeyboardButton(text="🚫 Ban User", callback_data="adm_ban"),
            InlineKeyboardButton(text="⚠️ Bot Health", callback_data="adm_health"),
        ],
        [
            InlineKeyboardButton(text="🔙 Back", callback_data="back_home"),
        ],
    ])


@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("❌ Not allowed", show_alert=True)

    text = (
        "👑 <b>ADMIN DASHBOARD</b>\n"
        "━━━━━━━━━━━━━━\n"
        "Control Panel Active\n"
        "━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(text, reply_markup=admin_dashboard_kb())
    await call.answer()
