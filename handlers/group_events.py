import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID
from database import db

router = Router()

# ================= OWNER CHECK =================
def is_owner(user_id: int):
    return user_id == OWNER_ID

# ================= PANEL =================
@router.message(F.text == "/panel")
async def panel(message: Message):

    if not is_owner(message.from_user.id):
        return await message.reply("❌ No access")

    status = await db.get_setting("maintenance")  # dari DB

    status_text = "🔴 ON" if status else "🟢 OFF"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"🔧 Maintenance: {status_text}",
                callback_data="toggle_maintenance"
            )
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast", callback_data="broadcast_menu"),
            InlineKeyboardButton(text="📊 Stats", callback_data="stats_menu")
        ]
    ])

    await message.answer(
        "🛠 <b>ROSE PRO PANEL</b>\n\nControl Center",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ================= TOGGLE MAINTENANCE (DB VERSION) =================
@router.callback_query(F.data == "toggle_maintenance")
async def toggle_maintenance(callback: CallbackQuery):

    if not is_owner(callback.from_user.id):
        return await callback.answer("No access", show_alert=True)

    current = await db.get_setting("maintenance")
    new_status = not current

    await db.set_setting("maintenance", new_status)

    status_text = "ON 🔴" if new_status else "OFF 🟢"

    await callback.message.edit_text(
        f"🛠 <b>MAINTENANCE</b>\nStatus: {status_text}",
        parse_mode="HTML"
    )

    await callback.answer("Updated")

# ================= STATS =================
@router.callback_query(F.data == "stats_menu")
async def stats(callback: CallbackQuery):

    if not is_owner(callback.from_user.id):
        return await callback.answer("No access", show_alert=True)

    users = await db.count_users()
    groups = await db.count_groups()

    await callback.message.edit_text(
        "📊 <b>REAL STATS</b>\n\n"
        f"👤 Users: {users}\n"
        f"👥 Groups: {groups}",
        parse_mode="HTML"
    )

    await callback.answer()

# ================= BROADCAST =================
@router.message(F.text.startswith("/broadcast"))
async def broadcast(message: Message, bot):

    if not is_owner(message.from_user.id):
        return

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        return await message.reply("Usage: /broadcast <text>")

    users = await db.get_all_users() or []

    msg = await message.reply("📢 Sending broadcast...")

    sent = 0

    for user_id in users:
        try:
            await bot.send_message(user_id, f"📢 {text}")
            sent += 1
            await asyncio.sleep(0.03)
        except:
            continue

    await msg.edit_text(f"✅ Sent to {sent} users")
