@router.message(
    CommandStart(),
    F.chat.type == "private"
)
async def start_private(
    message: Message
):

    user = message.from_user

    try:
        await db.add_user(user.id)
        users = await db.count_users()
        groups = await db.count_groups()
    except Exception as e:
        print(f"Database Error: {e}")
        users = 0
        groups = 0

    bot_username = message.bot.username

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Tambahkan ke Grup",
                    url=f"https://t.me/{bot_username}?startgroup=true"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Bantuan",
                    callback_data="help_menu"
                ),
                InlineKeyboardButton(
                    text="📊 Statistik",
                    callback_data="bot_stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❤️ Dukungan",
                    url="https://t.me/yourchannel"
                )
            ]
        ]
    )

    text = (
        f"👋 Halo {user.first_name}!\n\n"
        f"Saya adalah bot moderator grup yang membantu "
        f"mengelola grup dengan lebih mudah dan aman.\n\n"
        f"👤 Pengguna: {users}\n"
        f"👥 Grup: {groups}"
    )

    await message.answer(
        text,
        reply_markup=keyboard
    )
