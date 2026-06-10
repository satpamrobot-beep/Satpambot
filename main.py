import asyncio
import sys
import os

# =========================
# FIX PATH (WAJIB PALING ATAS)
# =========================
sys.path.insert(0, os.getcwd())

print("PROJECT ROOT FILES:", os.listdir("."))


from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import BOT_TOKEN
from db.pool import init_db
from bot.router import router


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # init db
    await init_db()

    # register router
    dp.include_router(router)

    print("🔥 BOT STARTED")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
