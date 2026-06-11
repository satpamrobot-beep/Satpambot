from datetime import datetime
import time
from aiogram.exceptions import TelegramBadRequest
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db.users import get_user_balance
from db.pool import get_pool
from handlers.start import dashboard_text, dashboard_kb

router = Router()

YEAR = datetime.now().year
COPYRIGHT = f"© {YEAR} EarnFileBot • Monetization System to Telegram"


# =========================
# CACHE FAST (FIXED)
# =========================
CACHE = {
    "users": 0,
    "uploads": 0,
    "last_update": 0
}

CACHE_TTL = 30  # detik


async def get_stats():
    now = time.time()

    # pakai cache kalau masih fresh
    if now - CACHE["last_update"] < CACHE_TTL:
        return CACHE["users"], CACHE["uploads"]

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            uploads = await conn.fetchval("SELECT COUNT(*) FROM uploads") or 0

        CACHE["users"] = users
        CACHE["uploads"] = uploads
        CACHE["last_update"] = now

        return users, uploads

    except:
        return CACHE["users"], CACHE["uploads"]


# =========================
# KEYBOARD
# =========================
def about_kb(active="home"):
    def mark(name, text):
        return f"👉 {text}" if active == name else text

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=mark("home", "📌 Ringkasan"), callback_data="about_home"),
            InlineKeyboardButton(text=mark("system", "⚙️ Sistem"), callback_data="about_system"),
        ],
        [
            InlineKeyboardButton(text=mark("features", "🚀 Fitur"), callback_data="about_features"),
            InlineKeyboardButton(text=mark("stats", "📊 Statistik"), callback_data="about_stats"),
        ],
        [
            InlineKeyboardButton(text=mark("earn", "💰 Monetisasi"), callback_data="about_earn"),
            InlineKeyboardButton(text=mark("vip", "👑 VIP"), callback_data="about_vip"),
        ],
        [
            InlineKeyboardButton(text="🔙 Kembali", callback_data="back_home"),
        ]
    ])


# =========================
# CONTENT ENGINE (FAST CLEAN)
# =========================
def content(tab, user, balance, users, uploads):

    user_id = user.id
    footer = f"\n\n<i>{COPYRIGHT}</i>"

    # ================= HOME =================
    if tab == "home":
        return (
            "╔══════════════════════════╗\n"
            " 🤖 <b>EARN FILE BOT</b>\n"
            "╚══════════════════════════╝\n\n"

            "📌 <b>Ringkasan Sistem</b>\n"
            "EarnFileBot adalah platform monetisasi file digital berbasis Telegram.\n"
            "Sistem ini memungkinkan user upload file, membuat kode unik, dan menghasilkan uang dari file berbayar.\n\n"

            "⚡ <b>Konsep Sistem:</b>\n"
            "• Upload file ke bot\n"
            "• Bot generate kode unik\n"
            "• Share link ke publik\n"
            "• User lain membeli file\n"
            "• Balance otomatis masuk ke akun kamu\n\n"

            f"🆔 ID User : <code>{user_id}</code>\n"
            f"💰 Saldo   : Rp {balance:,.0f}\n"
            f"👥 Users   : {users}\n"
            f"📦 Upload  : {uploads}\n\n"

            "🚀 Platform monetisasi file otomatis & scalable"
            + footer
        )

    # ================= SYSTEM =================
    if tab == "system":
        return (
            "⚙️ <b>SISTEM PLATFORM</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "🔧 <b>Backend Technology</b>\n"
            "• Python AsyncIO (non-blocking system)\n"
            "• Aiogram 3.x (Telegram Bot Framework)\n"
            "• PostgreSQL Pooler (database scalable)\n\n"

            "🚀 <b>Arsitektur Sistem</b>\n"
            "• Event-driven architecture\n"
            "• High concurrency support\n"
            "• Fast response API handling\n"
            "• Cloud-ready deployment\n\n"

            "⚡ <b>Performance</b>\n"
            "• Support ribuan user simultan\n"
            "• Optimized query database\n"
            "• Minimal latency system"
            + footer
        )

    # ================= FEATURES =================
    if tab == "features":
        return (
            "🚀 <b>FITUR UTAMA</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "📤 <b>Upload System</b>\n"
            "• Upload foto, video, dokumen\n"
            "• Generate kode unik otomatis\n"
            "• File tersimpan aman di database\n\n"

            "🔗 <b>Share System</b>\n"
            "• Link file unik untuk setiap upload\n"
            "• Bisa dibagikan ke Telegram / WhatsApp / TikTok\n"
            "• Tracking akses file\n\n"

            "💰 <b>Monetisasi System</b>\n"
            "• Upload GRATIS atau BERBAYAR\n"
            "• File berbayar menghasilkan saldo\n"
            "• Setiap pembelian masuk ke balance user\n\n"

            "📦 <b>File Management</b>\n"
            "• Akses file kapan saja\n"
            "• Riwayat upload tersimpan\n"
            "• Data aman di database\n\n"

            "📈 <b>Growth System</b>\n"
            "• Semakin banyak share = semakin besar income\n"
            "• Sistem dirancang untuk viral distribution"
            + footer
        )

    # ================= STATS =================
    if tab == "stats":
        return (
            "📊 <b>STATISTIK LIVE</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            f"👥 Total User   : {users}\n"
            f"📦 Total Upload : {uploads}\n\n"

            "📡 <b>System Status</b>\n"
            "• Real-time database tracking\n"
            "• Auto update statistik\n"
            "• Monitoring aktif 24/7\n\n"

            "📈 Platform terus berkembang setiap hari"
            + footer
        )

    # ================= EARN =================
    if tab == "earn":
        return (
            "💰 <b>MONETISASI & PENGHASILAN</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "📦 <b>Cara Kerja Sistem:</b>\n"
            "1. Upload file ke bot\n"
            "2. Set harga (FREE / PAID)\n"
            "3. Bot generate kode unik file\n"
            "4. Share link ke sosial media\n"
            "5. User lain membeli file\n"
            "6. Balance otomatis masuk\n\n"

            "💳 <b>Sumber Penghasilan:</b>\n"
            "• File BERBAYAR = income utama\n"
            "• File GRATIS = traffic generator\n"
            "• Semakin banyak pembeli = semakin besar saldo\n\n"

            "📢 <b>Strategi Cuan:</b>\n"
            "• Share ke Telegram group besar\n"
            "• WhatsApp / TikTok / Instagram\n"
            "• Gunakan file yang viral & dibutuhkan\n\n"

            "🔥 <b>Tips Pro:</b>\n"
            "• Jangan hanya upload, tapi promosi\n"
            "• Gunakan judul menarik\n"
            "• Konsisten upload file\n\n"

            "⚠️ Semua penghasilan berasal dari transaksi file berbayar"
            + footer
        )

    # ================= VIP =================
    if tab == "vip":
        return (
            "👑 <b>VIP / VVIP ACCESS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"

            "🚀 <b>Keuntungan VIP:</b>\n"
            "• Upload lebih cepat\n"
            "• Prioritas server\n"
            "• Akses fitur premium\n"
            "• Support prioritas admin\n\n"

            "🔥 <b>VVIP CHANNEL</b>\n"
            "Join sekarang di Channel VVIP EARNFILE:\n"
            "• Akses semua kode tanpa batas\n"
            "• Update file setiap hari\n"
            "• File premium eksklusif\n"
            "• Tidak semua user bisa masuk\n\n"

            "📢 <b>Benefit Tambahan:</b>\n"
            "Semakin aktif di VVIP, semakin besar peluang dapat file gratis & bonus income\n\n"

            "💡 Upgrade ke VVIP untuk full access system"
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
    users, uploads = await get_stats()

    try:
        await call.message.edit_text(
            content("home", user, balance, users, uploads),
            reply_markup=about_kb("home")
        )
    except TelegramBadRequest:
        pass

    await call.answer()
# =========================
# SWITCH TAB (ANTI ERROR FIX)
# =========================
@router.callback_query(F.data.startswith("about_"))
async def switch(call: CallbackQuery):
    user = call.from_user
    tab = call.data.replace("about_", "")

    allowed = {"home", "system", "features", "stats", "earn", "vip"}
    if tab not in allowed:
        return await call.answer()

    balance = await get_user_balance(user.id)
    users, uploads = await get_stats()

    new_text = content(tab, user, balance, users, uploads)
    new_kb = about_kb(tab)

    # 🔥 CEGAH EDIT SAMA (BIAR GAK ERROR)
    current = call.message.text or ""
    if current and tab in current:
        return await call.answer()

    try:
        await call.message.edit_text(
            new_text,
            reply_markup=new_kb
        )
    except TelegramBadRequest:
        # kalau masih sama / telegram nolak → skip aja
        pass

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
