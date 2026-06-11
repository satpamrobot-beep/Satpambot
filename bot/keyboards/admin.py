from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


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
            InlineKeyboardButton(text="🚫 Ban/Unban User", callback_data="adm_ban"),
            InlineKeyboardButton(text="⚠️ Bot Check", callback_data="adm_health"),
        ],
    ])
