import asyncio
import sys
import os

sys.path.insert(0, os.getcwd())

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from db.pool import init_db

# =========================
# HANDLERS IMPORT (SESUAI STRUKTUR KAMU)
# =========================
from handlers import start
from handlers import user_callbacks
from handlers import admin_panel
from handlers import admin_callbacks


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    await init_db()

    # register routers
    dp.include_router(start.router)
    dp.include_router(user_callbacks.router)
    dp.include_router(admin_panel.router)
    dp.include_router(admin_callbacks.router)

    print("🔥 BOT RUNNING (PRODUCTION READY)")

    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
