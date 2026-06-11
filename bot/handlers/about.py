from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db.users import get_user_balance
from db.pool import get_pool
from handlers.start import dashboard_text, dashboard_kb

router = Router()

YEAR = datetime.now().year

# =========================
# LANGUAGE CACHE
# =========================
user_lang = {}  # user_id -> "id" / "en"


# =========================
# DATABASE STATS
# =========================
async def total_users():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) FROM users")
            return row[0] or 0
    except:
        return 0


async def total_uploads():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) FROM uploads")
            return row[0] or 0
    except:
        return 0


# =========================
# KEYBOARD
# =========================
def about_kb(active="home"):
    def mark(name, text):
        return f"👉 {text}" if active == name else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=mark("home", "📌 Ringkasan"),
                callback_data="about_home"
            ),
            InlineKeyboardButton(
                text=mark("system", "⚙️ Sistem"),
                callback_data="about_system"
            ),
        ],
        [
            InlineKeyboardButton(
                text=mark("features", "🚀 Fitur"),
                callback_data="about_features"
            ),
            InlineKeyboardButton(
                text=mark("stats", "📊 Statistik"),
                callback_data="about_stats"
            ),
        ],
        [
            InlineKeyboardButton(
                text=mark("earn", "💰 Cara Cuan"),
                callback_data="about_earn"
            ),
            InlineKeyboardButton(
                text=mark("vip", "👑 VIP"),
                callback_data="about_vip"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🌍 Ganti Bahasa",
                callback_data="about_lang"
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔙 Kembali",
                callback_data="back_home"
            ),
        ]
    ])

# =========================
# CONTENT ENGINE
# =========================
def content(tab, user, balance, users, uploads, lang="id"):

    username = f"@{user.username}" if user.username else "-"

    # ================= INDONESIA =================
    if lang == "id":

        if tab == "home":
            return (
                "╔══════════════════════╗\n"
                " 🤖 EARN FILE BOT\n"
                "╚══════════════════════╝\n\n"

                "📌 <b>Ringkasan Sistem</b>\n"
                "Bot ini adalah platform upload & monetisasi file otomatis di Telegram.\n\n"

                f"👤 User : {username}\n"
                f"🆔 ID   : <code>{user.id}</code>\n"
                f"💰 Saldo: Rp {balance:,.0f}\n\n"

                "⚡ Sistem berbasis aktivitas pengguna"
            )

        if tab == "system":
            return (
                "⚙️ <b>Sistem</b>\n"
                "━━━━━━━━━━━━━━\n"
                "• Python AsyncIO\n"
                "• Aiogram 3.x\n"
                "• PostgreSQL Pooler\n"
                "• Sistem cepat & scalable"
            )

        if tab == "features":
            return (
                "🚀 <b>Fitur</b>\n"
                "━━━━━━━━━━━━━━\n"
                "• Upload file otomatis\n"
                "• Kode file unik\n"
                "• Share link publik\n"
                "• Sistem balance user"
            )

        if tab == "stats":
            return (
                "📊 <b>Statistik Live</b>\n"
                "━━━━━━━━━━━━━━\n"
                f"👥 Users  : {users}\n"
                f"📦 Upload : {uploads}"
            )

        if tab == "earn":
            return (
                "💰 <b>Monetisasi System</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                "📦 Upload file ke bot\n"
                "💵 Tentukan harga (Free / Paid)\n"
                "🔗 Dapatkan link share unik\n"
                "📢 Share ke sosial media\n\n"

                "📈 Aktivitas dapat meningkatkan potensi balance\n"
                "⚠️ Withdraw mengikuti aturan sistem"
            )

        if tab == "vip":
            return (
                "👑 <b>VIP</b>\n"
                "━━━━━━━━━━━━━━\n"
                "• Upload lebih cepat\n"
                "• Prioritas server\n"
                "• Fitur tambahan\n\n"
                "Status: Free User"
            )

        copyright_text = f"© {YEAR} EarnFileBot • Monetization System to Telegram"

    # ================= ENGLISH =================
    else:

        if tab == "home":
            return (
                "╔══════════════════════╗\n"
                " 🤖 EARN FILE BOT\n"
                "╚══════════════════════╝\n\n"

                "📌 <b>Overview</b>\n"
                "This bot is an automated file upload and monetization system on Telegram.\n\n"

                f"👤 User : {username}\n"
                f"🆔 ID   : <code>{user.id}</code>\n"
                f"💰 Balance : Rp {balance:,.0f}\n\n"

                "⚡ Activity-based reward system"
            )

        if tab == "system":
            return (
                "⚙️ <b>System Architecture</b>\n"
                "━━━━━━━━━━━━━━\n"
                "• Python AsyncIO\n"
                "• Aiogram 3.x\n"
                "• PostgreSQL Pooler\n"
                "• High performance scalable system"
            )

        if tab == "features":
            return (
                "🚀 <b>Features</b>\n"
                "━━━━━━━━━━━━━━\n"
                "• Automated file upload\n"
                "• Unique file code generator\n"
                "• Shareable public links\n"
                "• User balance system"
            )

        if tab == "stats":
            return (
                "📊 <b>Live Statistics</b>\n"
                "━━━━━━━━━━━━━━\n"
                f"👥 Total Users  : {users}\n"
                f"📦 Total Uploads: {uploads}"
            )

        if tab == "earn":
            return (
                "💰 <b>Monetization System</b>\n"
                "━━━━━━━━━━━━━━\n\n"

                "📦 Upload your files\n"
                "💵 Set price (Free / Paid)\n"
                "🔗 Generate shareable link\n"
                "📢 Promote on social media\n\n"

                "📈 Higher activity may increase balance growth\n"
                "⚠️ Withdrawals depend on system rules"
            )

        if tab == "vip":
            return (
                "👑 <b>VIP System</b>\n"
                "━━━━━━━━━━━━━━\n"
                "• Faster uploads\n"
                "• Priority processing\n"
                "• Extra features\n\n"
                "Status: Free User"
            )

        copyright_text = f"© {YEAR} EarnFileBot • Monetization System to Telegram"

    return copyright_text


# =========================
# MAIN ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    user = call.from_user
    lang = user_lang.get(user.id, "id")

    balance = await get_user_balance(user.id)
    users = await total_users()
    uploads = await total_uploads()

    await call.message.edit_text(
        content("home", user, balance, users, uploads, lang),
        reply_markup=about_kb("home")
    )
    await call.answer()


# =========================
# TAB SWITCH
# =========================
@router.callback_query(F.data.startswith("about_"))
async def switch(call: CallbackQuery):
    user = call.from_user
    lang = user_lang.get(user.id, "id")

    tab = call.data.replace("about_", "")

    balance = await get_user_balance(user.id)
    users = await total_users()
    uploads = await total_uploads()

    await call.message.edit_text(
        content(tab, user, balance, users, uploads, lang),
        reply_markup=about_kb(tab)
    )
    await call.answer()


# =========================
# LANGUAGE TOGGLE
# =========================
@router.callback_query(F.data == "about_lang")
async def change_lang(call: CallbackQuery):
    user = call.from_user

    current = user_lang.get(user.id, "id")
    user_lang[user.id] = "en" if current == "id" else "id"

    lang = user_lang[user.id]

    balance = await get_user_balance(user.id)
    users = await total_users()
    uploads = await total_uploads()

    await call.message.edit_text(
        content("home", user, balance, users, uploads, lang),
        reply_markup=about_kb("home")
    )
    await call.answer()


# =========================
# BACK HOME
# =========================
@router.callback_query(F.data == "back_home")
async def back(call: CallbackQuery):
    user = call.from_user
    balance = await get_user_balance(user.id)

    await call.message.edit_text(
        dashboard_text(user, balance),
        reply_markup=dashboard_kb()
    )
    await call.answer()
