from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

router = Router()


# =========================
# LOCKED PANEL
# =========================

@router.callback_query(
    F.data == "locked_panel"
)
async def locked_panel(
    call: CallbackQuery
):

    await call.answer(
        "Promote bot menjadi admin dulu.",
        show_alert=True
    )


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
# MODERATION MENU
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
                    callback_data="open_warns"
                ),

                InlineKeyboardButton(
                    text="🔨 Bans",
                    callback_data="open_bans"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔇 Mutes",
                    callback_data="open_mutes"
                ),

                InlineKeyboardButton(
                    text="🚨 Reports",
                    callback_data="open_reports"
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
        "👥 Moderation Menu",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# PROTECTION MENU
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
                    callback_data="open_locks"
                ),

                InlineKeyboardButton(
                    text="🚫 Filters",
                    callback_data="open_filters"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🛑 Flood",
                    callback_data="open_flood"
                ),

                InlineKeyboardButton(
                    text="⏳ Cooldown",
                    callback_data="open_cooldown"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🤖 Captcha",
                    callback_data="open_captcha"
                ),

                InlineKeyboardButton(
                    text="🚷 Anti Spam",
                    callback_data="open_antispam"
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
        "🛡 Protection Menu",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# GREETINGS MENU
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
                    callback_data="open_welcome"
                ),

                InlineKeyboardButton(
                    text="🚪 Leave",
                    callback_data="open_leave"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📥 Join Logs",
                    callback_data="open_joinlogs"
                ),

                InlineKeyboardButton(
                    text="📤 Leave Logs",
                    callback_data="open_leavelogs"
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
        "💬 Greetings Menu",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# STATS MENU
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
        "📊 Statistics Menu",
        reply_markup=keyboard
    )

    await call.answer()


# =========================
# SETTINGS MENU
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
                    callback_data="open_config"
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
        "⚙ Settings Menu",
        reply_markup=keyboard
    )

    await call.answer()
