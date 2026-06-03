import asyncio
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers import admin, moderation, welcome

async def main():

    print("🚀 Starting bot...")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN KOSONG")
        return

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    try:
        dp.include_router(admin.router)
        dp.include_router(moderation.router)
        dp.include_router(welcome.router)
    except Exception as e:
        print("❌ ROUTER ERROR:", e)
        return

    print("🤖 Bot running...")

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ CRASH ERROR:", e)
