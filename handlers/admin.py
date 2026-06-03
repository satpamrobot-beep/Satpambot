import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID, MAINTENANCE_MODE
from database import db

router = Router()

# ================= OWNER CHECK =================
def is_owner(user_id: int):
    return user_id == OWNER_ID

# ================= ADMIN PANEL =================
@router.message(F.text == "/panel")
async def panel(message: Message):

    if not is_owner(message.from_user.id):
        return await message.reply("❌ No access")

    status = "🔴 ON" if MAINTENANCE_MODE else "🟢 OFF"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🔧 Maintenance: {status}",
                callback_data="toggle_maintenance"
            )
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="broadcast_menu"),
            InlineKeyboardButton(text="📊 Stats", callback_data="stats_menu")
        ]
    ])

    await message.answer(
        "🛠 <b>ROSE PRO PANEL</b>\n\n"
        "⚙️ Control System Bot",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ================= TOGGLE MAINTENANCE =================
@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance(callback: CallbackQuery):

    global MAINTENANCE_MODE

    if callback.from_user.id != OWNER_ID:
        return await callback.answer("No access", show_alert=True)

    MAINTENANCE_MODE = not MAINTENANCE_MODE

    status = "ON 🔴" if MAINTENANCE_MODE else "OFF 🟢"

    await callback.message.edit_text(
        f"🛠 <b>MAINTENANCE</b>\n\nStatus: {status}",
        parse_mode="HTML"
    )

    await callback.answer("Updated")

# ================= STATS REAL =================
@router.callback_query(F.data == "stats_menu")
async def stats(callback: CallbackQuery):

    users = await db.count_users()
    groups = await db.count_groups()

    await callback.message.answer(
        "📊 <b>REAL STATS</b>\n\n"
        f"👤 Users: {users}\n"
        f"👥 Groups: {groups}",
        parse_mode="HTML"
    )

    await callback.answer()

# ================= BROADCAST SYSTEM =================
broadcast_cache = {}

@router.callback_query(F.data == "broadcast_menu")
async def broadcast_menu(callback: CallbackQuery):

    if callback.from_user.id != OWNER_ID:
        return await callback.answer("No access", show_alert=True)

    await callback.message.answer(
        "📢 Kirim pesan broadcast:\n\n"
        "Ketik:\n/broadcast pesan kamu"
    )

    await callback.answer()

@router.message(F.text.startswith("/broadcast"))
async def broadcast(message: Message, bot):

    if not is_owner(message.from_user.id):
        return

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        return await message.reply("Usage: /broadcast <text>")

    users = await db.get_all_users()

    sent = 0

    msg = await message.reply("📢 Sending broadcast...")

    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 {text}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            continue

    await msg.edit_text(f"✅ Sent to {sent} users")
