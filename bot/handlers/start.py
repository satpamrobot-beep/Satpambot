from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.database import get_pool

router = Router()


# =========================
# KEYBOARD HOME
# =========================
def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📤 Upload", callback_data="upload"),
            InlineKeyboardButton(text="🔎 Buka Code", callback_data="open_code")
        ],
        [
            InlineKeyboardButton(text="📦 Produk Saya", callback_data="my_product"),
            InlineKeyboardButton(text="💰 Saldo", callback_data="balance")
        ],
        [
            InlineKeyboardButton(text="❓ Help", callback_data="help"),
            InlineKeyboardButton(text="ℹ️ About", callback_data="about")
        ]
    ])


# =========================
# FORCE SUB (SIMPLE CHECK)
# =========================
async def check_join(bot, user_id: int, channel_id: str):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


# =========================
# /START
# =========================
@router.message(CommandStart())
async def start(message: Message, bot):
    user = message.from_user
    pool = get_pool()

    # =====================
    # AUTO REGISTER USER
    # =====================
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO NOTHING
        """, user.id, user.username)

    # =====================
    # FORCE SUB CHECK
    # =====================
    CHANNEL = "@your_channel"
    GROUP = "@your_group"

    try:
        ch = await check_join(bot, user.id, CHANNEL)
        gp = await check_join(bot, user.id, GROUP)

        if not ch or not gp:
            await message.answer(
                "⚠️ Kamu harus join channel & group dulu sebelum menggunakan bot."
            )
            return
    except:
        pass

    # =====================
    # SHOW HOME
    # =====================
    await message.answer(
        "🤖 <b>EarnFile Bot</b>\nUpload • Sell • Earn",
        reply_markup=home_kb(),
        parse_mode="HTML"
    )


# =========================
# HOME BUTTON (REFRESH)
# =========================
@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery):
    await callback.message.edit_text(
        "🤖 <b>EarnFile Bot</b>\nUpload • Sell • Earn",
        reply_markup=home_kb(),
        parse_mode="HTML"
    )
    await callback.answer()


# =========================
# HELP
# =========================
@router.callback_query(F.data == "help")
async def help_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Cara Upload", callback_data="help_upload")],
        [InlineKeyboardButton(text="📌 Cara Get File", callback_data="help_getfile")],
        [InlineKeyboardButton(text="📌 Cara Cuan", callback_data="help_earn")],
        [InlineKeyboardButton(text="📌 Withdraw", callback_data="help_wd")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="home")]
    ])

    await callback.message.edit_text(
        "❓ <b>Help Center</b>\nPilih menu bantuan:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


# =========================
# ABOUT
# =========================
@router.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ <b>About EarnFile</b>\n\nUpload • Sell • Earn\nMarketplace file & media system.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back", callback_data="home")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()
