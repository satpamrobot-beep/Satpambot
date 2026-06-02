import asyncio
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import db

from handlers import admin, moderation

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    await db.connect()
    await db.init()

    dp.include_router(admin.router)
    dp.include_router(moderation.router)

    print("Bot running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
