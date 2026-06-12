import asyncio
from aiogram import Bot, Dispatcher
from bot.loader import bot, dp

from bot.db.database import connect_db, close_db

# import router semua handler (nanti kamu tambah satu-satu)
from bot.handlers import start


async def main():
    # 🔥 CONNECT DATABASE DULU
    await connect_db()

    # 🔥 REGISTER ROUTER
    dp.include_router(start.router)

    print("🤖 EarnFile Bot Running...")

    # 🔥 START BOT
    await dp.start_polling(bot)


# optional cleanup
async def on_shutdown():
    await close_db()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")
