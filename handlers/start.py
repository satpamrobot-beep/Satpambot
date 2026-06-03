from aiogram import Router, F
from aiogram.types import Message

router = Router()

# =========================
# SIMPLE IN-MEMORY STORAGE (DEV MODE)
# nanti bisa upgrade ke Supabase
# =========================
welcome_text = {}

# =========================
# BOT + USER JOIN HANDLER
# =========================
@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message):

    for user in message.new_chat_members:

        # ================= BOT JOIN (SETUP WIZARD) =================
        if user.is_bot:

            await message.answer(
                "🤖 <b>SATPAM BOT SUCCESSFULLY ADDED</b>\n\n"
                "⚙️ <b>SETUP REQUIRED</b>\n"
                "1. Jadikan bot ADMIN\n"
                "2. Aktifkan izin berikut:\n"
                "   • Delete Messages\n"
                "   • Ban Users\n"
                "   • Restrict Users\n\n"
                "📌 Setelah setup selesai:\n"
                "• Ketik /help untuk melihat fitur\n"
                "• Ketik /panel (owner only)\n\n"
                "🚀 Bot siap digunakan di group ini!",
                parse_mode="HTML"
            )
            return

        # ================= USER JOIN (WELCOME SYSTEM) =================
        text = welcome_text.get(
            message.chat.id,
            None
        )

        # DEFAULT WELCOME (kalau belum diset)
        if not text:
            text = (
                "👋 <b>Welcome {user}</b>\n\n"
                "Selamat datang di group!\n"
                "Jangan spam & baca rules ya 🙂"
            )

        await message.answer(
            text.replace("{user}", user.full_name),
            parse_mode="HTML"
        )

# =========================
# SET WELCOME MESSAGE
# =========================
@router.message(F.text.startswith("/setwelcome"))
async def set_welcome(message: Message):

    if message.chat.type not in ["group", "supergroup"]:
        return await message.reply("❌ Command ini hanya untuk group")

    if not message.reply_to_message:
        return await message.reply("❌ Reply pesan untuk dijadikan welcome")

    welcome_text[message.chat.id] = message.reply_to_message.text

    await message.reply(
        "✅ <b>WELCOME MESSAGE UPDATED</b>\n\n"
        "📌 Pesan welcome baru sudah disimpan untuk group ini",
        parse_mode="HTML"
    )

# =========================
# RESET WELCOME
# =========================
@router.message(F.text == "/resetwelcome")
async def reset_welcome(message: Message):

    if message.chat.id in welcome_text:
        del welcome_text[message.chat.id]

        await message.reply("♻️ Welcome message direset ke default")
    else:
        await message.reply("⚠️ Tidak ada custom welcome di group ini")

# =========================
# HELP SYSTEM (ANTI BINGUNG)
# =========================
@router.message(F.text == "/help")
async def help_group(message: Message):

    if message.chat.type in ["group", "supergroup"]:

        await message.reply(
            "🤖 <b>SATPAM BOT HELP MENU</b>\n\n"
            "👮 MODERATION:\n"
            "/ban (reply)\n"
            "/kick (reply)\n"
            "/mute (reply)\n"
            "/unmute (reply)\n"
            "/warn (reply)\n\n"
            "⚙️ SETUP:\n"
            "/setwelcome (reply pesan)\n"
            "/resetwelcome\n\n"
            "📌 Bot aktif & siap digunakan",
            parse_mode="HTML"
        )

    else:
        await message.answer(
            "🤖 Bot ini bekerja di group.\n\n"
            "➕ Add bot ke group untuk mulai menggunakan fitur."
        )
