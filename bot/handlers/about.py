from datetime import datetime
import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from db.users import get_user_balance
from db.pool import get_pool
from handlers.start import dashboard_text, dashboard_kb

router = Router()

YEAR = datetime.now().year
COPYRIGHT = f"© {YEAR} EarnFileBot • Monetization System to Telegram"


# =========================
# CACHE (BIAR GAK LAG)
# =========================
CACHE = {
    "users": 0,
    "uploads": 0,
    "last_update": 0
}

CACHE_TTL = 30  # detik


async def refresh_cache():
    now = asyncio.get_event_loop().time()
    if now - CACHE["last_update"] < CACHE_TTL:
        return

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            CACHE["users"] = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            CACHE["uploads"] = await conn.fetchval("SELECT COUNT(*) FROM uploads") or 0
            CACHE["last_update"] = now
    except:
        pass


async def get_stats():
    await refresh_cache()
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
# CONTENT ENGINE (FAST)
# =========================
def content(tab, user, balance, users, uploads):

    username = f"@{user.username}" if user.username else "-"
    footer = f"\n\n<i>{COPYRIGHT}</i>"

    if tab == "home":
        return (
            "🤖 <b>EARN FILE BOT</b>\n\n"
            "📌 Ringkasan Sistem\n"
            "Monetisasi file otomatis di Telegram.\n\n"
            f"👤 {username}\n"
            f"💰 Rp {balance:,.0f}\n"
            + footer
        )

    if tab == "system":
        return (
            "⚙️ Sistem\n"
            "• AsyncIO\n"
            "• Aiogram\n"
            "• PostgreSQL\n"
            "• Fast & scalable"
            + footer
        )

    if tab == "features":
        return (
            "🚀 Fitur\n"
            "• Upload file\n"
            "• Share link\n"
            "• Monetisasi file\n"
            "• Balance system"
            + footer
        )

    if tab == "stats":
        return (
            "📊 Statistik\n"
            f"👥 Users: {users}\n"
            f"📦 Upload: {uploads}"
            + footer
        )

    if tab == "earn":
        return (
            "💰 Monetisasi\n"
            "• Upload FREE / PAID\n"
            "• File berbayar = saldo masuk\n"
            "• Share link = income"
            + footer
        )

    if tab == "vip":
        return (
            "👑 VIP / VVIP\n"
            "• Akses full code\n"
            "• Update harian\n"
            "• Join channel VVIP EARNFILE\n"
            "• Unlimited access file"
            + footer
        )

    return footer


# =========================
# MAIN ABOUT (FAST RESPONSE)
# =========================
@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    user = call.from_user

    balance = await get_user_balance(user.id)
    users, uploads = await get_stats()

    await call.message.edit_text(
        content("home", user, balance, users, uploads),
        reply_markup=about_kb("home")
    )
    await call.answer()


# =========================
# SWITCH TAB (OPTIMIZED)
# =========================
@router.callback_query(F.data.startswith("about_"))
async def switch(call: CallbackQuery):
    user = call.from_user
    tab = call.data.replace("about_", "")

    if tab not in {"home", "system", "features", "stats", "earn", "vip"}:
        return await call.answer("Tab tidak valid", show_alert=True)

    balance = await get_user_balance(user.id)
    users, uploads = await get_stats()

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
