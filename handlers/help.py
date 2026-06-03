from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

router = Router()

# =========================
# MAIN /HELP MENU
# =========================
@router.message(F.text == "/help")
async def help_command(message: Message):

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👮 Moderation", callback_data="help_mod"),
            InlineKeyboardButton(text="⚙️ Setup Bot", callback_data="help_setup")
        ],
        [
            InlineKeyboardButton(text="📊 Stats", callback_data="stats_menu"),
            InlineKeyboardButton(text="🛠 How to Use", callback_data="help_guide")
        ]
    ])

    if message.chat.type == "private":

        await message.answer(
            "📖 <b>ROSE BOT HELP CENTER</b>\n\n"
            "👋 Welcome!\n\n"
            "🤖 Bot ini adalah <b>Group Management Bot</b>\n"
            "untuk mengelola Telegram group secara otomatis.\n\n"
            "📌 Pilih menu di bawah untuk panduan lengkap:",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    else:

        await message.reply(
            "📖 <b>ROSE HELP (GROUP MODE)</b>\n\n"
            "👮 Moderation:\n"
            "/ban /kick /mute /unmute /warn\n\n"
            "⚙️ Setup:\n"
            "/setwelcome /resetwelcome\n\n"
            "📊 Stats:\n"
            "/stats\n\n"
            "💡 Tips:\n"
            "Gunakan reply ke user saat pakai command",
            parse_mode="HTML"
        )

# =========================
# MODERATION HELP (DETAILED)
# =========================
@router.callback_query(F.data == "help_mod")
async def help_mod(callback: CallbackQuery):

    await callback.message.answer(
        "👮 <b>MODERATION GUIDE</b>\n\n"
        "📌 Cara pakai command:\n"
        "➡️ Semua command HARUS reply ke user\n\n"
        "🚫 /ban → Ban user dari group\n"
        "👢 /kick → Keluarkan user (bisa masuk lagi)\n"
        "🔇 /mute → Matikan chat user\n"
        "🔊 /unmute → Aktifkan chat lagi\n"
        "⚠️ /warn → Beri peringatan user\n\n"
        "💡 Contoh:\n"
        "Reply pesan user → ketik /ban",
        parse_mode="HTML"
    )
    await callback.answer()

# =========================
# SETUP HELP (STEP BY STEP)
# =========================
@router.callback_query(F.data == "help_setup")
async def help_setup(callback: CallbackQuery):

    await callback.message.answer(
        "⚙️ <b>BOT SETUP GUIDE</b>\n\n"
        "📌 Langkah wajib sebelum pakai bot:\n\n"
        "1️⃣ Tambahkan bot ke group\n"
        "2️⃣ Jadikan bot ADMIN\n"
        "3️⃣ Aktifkan permission:\n"
        "   • Delete messages\n"
        "   • Ban users\n"
        "   • Restrict users\n\n"
        "4️⃣ Ketik /help di group\n\n"
        "✅ Setelah itu bot langsung aktif\n\n"
        "⚠️ Jika tidak di admin → bot tidak bisa kerja",
        parse_mode="HTML"
    )
    await callback.answer()

# =========================
# HOW TO USE (ANTI BINGUNG MODE)
# =========================
@router.callback_query(F.data == "help_guide")
async def help_guide(callback: CallbackQuery):

    await callback.message.answer(
        "🛠 <b>HOW TO USE ROSE BOT</b>\n\n"
        "📌 BOT INI BUKAN BOT CHAT BIASA\n"
        "Tapi Group Manager Bot\n\n"
        "👤 Untuk USER:\n"
        "• Tinggal join group\n"
        "• Ikuti rules group\n\n"
        "👮 Untuk ADMIN:\n"
        "• Gunakan /ban /mute /warn\n"
        "• Reply ke user target\n\n"
        "⚙️ Untuk OWNER:\n"
        "• /panel untuk kontrol bot\n"
        "• broadcast & maintenance\n\n"
        "💡 Intinya:\n"
        "Bot ini otomatis menjaga group dari spam & toxic",
        parse_mode="HTML"
    )
    await callback.answer()
