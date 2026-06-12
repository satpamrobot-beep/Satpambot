import asyncio
from aiogram import Dispatcher
from bot.loader import bot, dp

from bot.db.database import init_db, close_db
from bot.handlers import start


async def main():
    await init_db()  # 🔥 CONNECT DB

    dp.include_router(start.router)

    print("🤖 EarnFile Bot Running...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
