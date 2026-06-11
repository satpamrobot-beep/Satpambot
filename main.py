import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from db.supabase import supabase  # optional check import

# handlers router
from handlers.start import router as start_router
from handlers.callback import router as callback_router
from handlers.code import router as code_router
from handlers.admin.panel import router as admin_router


# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================
# BOT INIT
# =========================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()


# =========================
# REGISTER ROUTERS
# =========================
dp.include_router(start_router)
dp.include_router(callback_router)
dp.include_router(code_router)
dp.include_router(admin_router)


# =========================
# START BOT
# =========================
async def main():
    logging.info("🚀 Bot is starting...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
