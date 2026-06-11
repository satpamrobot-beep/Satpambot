import asyncio

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart

from db.users import add_user, get_user_balance
from services.join import is_joined

router = Router()


# =========================
# FORCE JOIN BUTTON
# =========================
def force_join_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Join Channel",
                    url="https://t.me/+8TUGR4lwuzc4OTk1"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Join Group",
                    url="https://t.me/+1tipdp-NTywzODhl"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Check Join",
                    callback_data="check_join"
                )
            ]
        ]
    )


# =========================
# DASHBOARD BUTTONS
# =========================
def dashboard_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📤 UpFile",
                    callback_data="upfile"
                ),
                InlineKeyboardButton(
                    text="📥 GetFile",
                    callback_data="getfile"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Withdraw",
                    callback_data="withdraw"
                ),
                InlineKeyboardButton(
                    text="👤 Account",
                    callback_data="account"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Setting",
                    callback_data="setting"
                ),
                InlineKeyboardButton(
                    text="📊 Statistik",
                    callback_data="statistik"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Help",
                    callback_data="help"
                ),
                InlineKeyboardButton(
                    text="ℹ️ About",
                    callback_data="about"
                )
            ]
        ]
    )


# =========================
# DASHBOARD TEXT
# =========================
def dashboard_text(user, balance_rp: int):
    username = f"@{user.username}" if user.username else "Tidak ada"
    usd = balance_rp / 16000

    return (
        "╔══════════════════════╗\n"
        " 💰 𝗘𝗮𝗿𝗻 𝗙𝗶𝗹𝗲 𝗕𝗼𝘁 🤖\n"
        "╚══════════════════════╝\n\n"
        f"👤 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲\n"
        f"└ {username}\n\n"
        f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗\n"
        f"└ <code>{user.id}</code>\n\n"
        f"💳 𝗕𝗮𝗹𝗮𝗻𝗰𝗲\n"
        f"└ Rp {balance_rp:,.0f} / $ {usd:,.2f}\n\n"
        "╭────────────────────╮\n"
        "│ 🚀 𝗨𝗽𝗹𝗼𝗮𝗱 • 𝗦𝗵𝗮𝗿𝗲 • 𝗘𝗮𝗿𝗻 │\n"
        "╰────────────────────╯"
    )


# =========================
# START COMMAND
# =========================
@router.message(CommandStart())
async def start(message: Message):
    user = message.from_user

    try:
        await add_user(
            user.id,
            user.username,
            user.full_name
        )
    except Exception as e:
        print("[add_user error]", e)

    if not await is_joined(
        message.bot,
        user.id
    ):
        await message.answer(
            "⚠️ Kamu harus join Channel & Group terlebih dahulu.",
            reply_markup=force_join_kb()
        )
        return

    balance = await get_user_balance(user.id)

    msg = await message.answer(
        "⚡ 𝗟𝗼𝗮𝗱𝗶𝗻𝗴..."
    )

    await asyncio.sleep(0.4)

    await msg.edit_text(
        "👤 𝗟𝗼𝗮𝗱𝗶𝗻𝗴 𝗨𝘀𝗲𝗿..."
    )

    await asyncio.sleep(0.4)

    await msg.edit_text(
        "💳 𝗟𝗼𝗮𝗱𝗶𝗻𝗴 𝗕𝗮𝗹𝗮𝗻𝗰𝗲..."
    )

    await asyncio.sleep(0.4)

    await msg.edit_text(
        dashboard_text(
            user,
            balance
        ),
        reply_markup=dashboard_kb()
    )


# =========================
# CHECK JOIN
# =========================
@router.callback_query(
    F.data == "check_join"
)
async def check_join(call: CallbackQuery):
    user = call.from_user

    if await is_joined(
        call.bot,
        user.id
    ):
        balance = await get_user_balance(
            user.id
        )

        await call.message.edit_text(
            "✅ 𝗩𝗲𝗿𝗶𝗳𝘆𝗶𝗻𝗴..."
        )

        await asyncio.sleep(0.5)

        await call.message.edit_text(
            dashboard_text(
                user,
                balance
            ),
            reply_markup=dashboard_kb()
        )

        await call.answer()

    else:
        await call.answer(
            "❌ Kamu belum join semua",
            show_alert=True
        )
