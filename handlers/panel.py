from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

router = Router()


# =========================
# MAIN PANEL
# =========================

@router.callback_query(
    F.data == "admin_panel"
)
async def open_panel(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="👥 Moderation",
                    callback_data="panel_mod"
                ),

                InlineKeyboardButton(
                    text="🛡 Protection",
                    callback_data="panel_protect"
                )
            ],

            [
                InlineKeyboardButton(
                    text="💬 Greetings",
                    callback_data="panel_greet"
                ),

                InlineKeyboardButton(
                    text="📊 Statistics",
                    callback_data="panel_stats"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⚙ Settings",
                    callback_data="panel_settings"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "⚙ Admin Panel",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# MODERATION
# =========================

@router.callback_query(
    F.data == "panel_mod"
)
async def moderation_panel(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="⚠ Warns",
                    callback_data="mod_warns"
                ),

                InlineKeyboardButton(
                    text="🔨 Bans",
                    callback_data="mod_bans"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔇 Mutes",
                    callback_data="mod_mutes"
                ),

                InlineKeyboardButton(
                    text="🚨 Reports",
                    callback_data="mod_reports"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="admin_panel"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "👥 Moderation Panel",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# PROTECTION
# =========================

@router.callback_query(
    F.data == "panel_protect"
)
async def protection_panel(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🔒 Locks",
                    callback_data="protect_locks"
                ),

                InlineKeyboardButton(
                    text="🚫 Filters",
                    callback_data="protect_filters"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🛑 Flood",
                    callback_data="protect_flood"
                ),

                InlineKeyboardButton(
                    text="⏳ Cooldown",
                    callback_data="protect_cooldown"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🤖 Captcha",
                    callback_data="protect_captcha"
                ),

                InlineKeyboardButton(
                    text="🚷 Anti Spam",
                    callback_data="protect_antispam"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="admin_panel"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "🛡 Protection Panel",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# GREETINGS
# =========================

@router.callback_query(
    F.data == "panel_greet"
)
async def greetings_panel(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="👋 Welcome",
                    callback_data="greet_welcome"
                ),

                InlineKeyboardButton(
                    text="🚪 Leave",
                    callback_data="greet_leave"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📥 Join Logs",
                    callback_data="greet_join"
                ),

                InlineKeyboardButton(
                    text="📤 Leave Logs",
                    callback_data="greet_leave_logs"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="admin_panel"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "💬 Greetings Panel",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# STATISTICS
# =========================

@router.callback_query(
    F.data == "panel_stats"
)
async def stats_panel(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="👤 Users",
                    callback_data="stats_users"
                ),

                InlineKeyboardButton(
                    text="👥 Groups",
                    callback_data="stats_groups"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⚠ Warn Stats",
                    callback_data="stats_warns"
                ),

                InlineKeyboardButton(
                    text="🚨 Reports",
                    callback_data="stats_reports"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="admin_panel"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "📊 Statistics Panel",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# SETTINGS
# =========================

@router.callback_query(
    F.data == "panel_settings"
)
async def settings_panel(
    call: CallbackQuery
):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="⚙ Group Config",
                    callback_data="set_config"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅ Back",
                    callback_data="admin_panel"
                )
            ]
        ]
    )

    await call.message.edit_text(
        "⚙ Settings Panel",
        reply_markup=keyboard
    )

    await call.answer()
