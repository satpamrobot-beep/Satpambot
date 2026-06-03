import asyncio
import logging

from aiogram import Bot, Dispatcher
from config import BOT_TOKEN

from handlers import admin, moderation, welcome, start, help

# ⚠️ IMPORT PANEL HARUS ADA FILE-NYA
from handlers.panel import router as panel_router


logging.basicConfig(level=logging.INFO)

async def main():

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(moderation.router)
    dp.include_router(welcome.router)
    dp.include_router(help.router)

    dp.include_router(panel_router)

    print("🤖 Bot running...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
