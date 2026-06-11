from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db.users import get_user_balance
from db.pool import get_pool
from handlers.start import dashboard_text, dashboard_kb

router = Router()

YEAR = datetime.now().year
COPYRIGHT = f"© {YEAR} EarnFileBot • Monetization System to Telegram"


# =========================
# STATS
# =========================
async def total_users():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM users") or 0
    except:
        return 0


async def total_uploads():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM uploads") or 0
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
            InlineKeyboardButton(mark("home", "📌 Ringkasan"), callback_data="about_home"),
            InlineKeyboardButton(mark("system", "⚙️ Sistem"), callback_data="about_system"),
        ],
        [
            InlineKeyboardButton(mark("features", "🚀 Fitur"), callback_data="about_features"),
            InlineKeyboardButton(mark("stats", "📊 Statistik"), callback_data="about_stats"),
        ],
        [
            InlineKeyboardButton(mark("earn", "💰 Monetisasi"), callback_data="about_earn"),
            InlineKeyboardButton(mark("vip", "👑 VIP"), callback_data="about_vip"),
        ],
        [
            InlineKeyboardButton("🔙 Kembali", callback_data="back_home"),
        ]
    ])


# =========================
# CONTENT ENGINE
# =========================
def content(tab, user, balance, users, uploads):

    username = f"@{user.username}" if user.username else "-"
    footer = f"\n\n<i>{COPYRIGHT}</i>"

    # ================= HOME =================
    if tab == "home":
        return (
            "╔══════════════════════════╗\n"
            " 🤖 <b>EARN FILE BOT</b>\n"
            "╚══════════════════════════╝\n\n"

            "📌 <b>Ringkasan Sistem</b>\n"
            "EarnFileBot adalah platform monetisasi file digital berbasis Telegram.\n"
            "User dapat upload file, membuat kode unik, dan membagikan link untuk menghasilkan uang.\n\n"

            f"👤 User  : {username}\n"
            f"🆔 ID    : <code>{user.id}</code>\n"
            f"💰 Saldo : Rp {balance:,.0f}\n\n"

            "⚡ Sistem marketplace file digital + monetisasi otomatis"
            + footer
        )

    # ================= SYSTEM =================
    if tab == "system":
        return (
            "⚙️ <b>Sistem Platform</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "• Python AsyncIO Engine\n"
            "• Aiogram Telegram Bot API\n"
            "• PostgreSQL Pooler Database\n"
            "• High Performance Architecture\n"
            "• Scalable & Cloud Ready\n\n"

            "📡 Sistem mampu menangani ribuan user secara bersamaan tanpa delay"
            + footer
        )

    # ================= FEATURES =================
    if tab == "features":
        return (
            "🚀 <b>Fitur Utama</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "📤 Upload File\n"
            "• Foto, video, dokumen\n"
            "• Generate kode unik otomatis\n\n"

            "🔗 Share System\n"
            "• Link file bisa dibagikan ke sosial media\n"
            "• Tracking akses file\n\n"

            "💳 Monetisasi System\n"
            "• Upload GRATIS atau BERBAYAR\n"
            "• File berbayar menghasilkan saldo saat dibeli user lain\n\n"

            "📦 File Management\n"
            "• Akses file kapan saja\n"
            "• Data tersimpan aman di database"
            + footer
        )

    # ================= STATS =================
    if tab == "stats":
        return (
            "📊 <b>Statistik Live</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            f"👥 Total User   : {users}\n"
            f"📦 Total Upload : {uploads}\n\n"

            "⚡ Data update real-time dari database\n"
            "📈 Sistem terus berkembang setiap hari"
            + footer
        )

    # ================= EARN =================
    if tab == "earn":
        return (
            "💰 <b>Monetisasi & Penghasilan</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "📦 <b>Cara Kerja:</b>\n"
            "1. Upload file ke bot\n"
            "2. Set harga (Free / Paid)\n"
            "3. Bot membuat kode unik file\n"
            "4. Share link ke sosial media\n\n"

            "💳 <b>Sistem Penghasilan:</b>\n"
            "• File GRATIS → tidak menghasilkan\n"
            "• File BERBAYAR → setiap pembelian masuk saldo otomatis\n"
            "• Semakin banyak pembeli = semakin besar penghasilan\n\n"

            "📢 <b>Strategi Cuan:</b>\n"
            "• Share ke Telegram group\n"
            "• WhatsApp / TikTok / Instagram\n"
            "• Gunakan file yang viral / dibutuhkan orang\n\n"

            "🔥 <b>Tips Pro:</b>\n"
            "• Jangan cuma upload, tapi juga promosi\n"
            "• Konsisten upload file berkualitas\n"
            "• Gunakan judul menarik biar banyak klik"
            + footer
        )

    # ================= VIP (UPDATED VVIP) =================
    if tab == "vip":
        return (
            "👑 <b>VIP / VVIP ACCESS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "🚀 <b>Keuntungan VIP:</b>\n"
            "• update media setiap hari\n"
            "• Prioritas update tanpa batas\n"
            "• Fitur premium unlock\n"
            "• Support prioritas admin\n\n"

            "🔥 <b>VVIP ACCESS (RECOMMENDED)</b>\n"
            "• Join Channel VVIP EARNFILE\n"
            "• Dapat akses semua code tanpa batas\n"
            "• Update code baru setiap hari\n"
            "• Akses file premium eksklusif\n\n"

            "📢 <b>Info Penting:</b>\n"
            "Semakin aktif di VVIP, semakin besar peluang mendapatkan media gratis file tanpa berbayar.\n\n"

            "💡 Upgrade ke VVIP untuk mendapakan media full update"
            + footer
        )

    return footer


# =========================
# MAIN ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    user = call.from_user

    balance = await get_user_balance(user.id)
    users = await total_users()
    uploads = await total_uploads()

    await call.message.edit_text(
        content("home", user, balance, users, uploads),
        reply_markup=about_kb("home")
    )
    await call.answer()


# =========================
# TAB SWITCH
# =========================
@router.callback_query(F.data.startswith("about_"))
async def switch(call: CallbackQuery):
    user = call.from_user
    tab = call.data.replace("about_", "")

    allowed = {"home", "system", "features", "stats", "earn", "vip"}
    if tab not in allowed:
        return await call.answer("Tab tidak valid", show_alert=True)

    balance = await get_user_balance(user.id)
    users = await total_users()
    uploads = await total_uploads()

    await call.message.edit_text(
        content(tab, user, balance, users, uploads),
        reply_markup=about_kb(tab)
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
