import asyncio
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers import admin, moderation, welcome, start
from handlers import help

async def main():

    print("🚀 Bot starting...")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # routers
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(moderation.router)
    dp.include_router(welcome.router)
    dp.include_router(help.router)

    print("🤖 Bot running...")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
