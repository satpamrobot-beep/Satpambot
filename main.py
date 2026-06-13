import asyncio

from aiogram import Dispatcher

from bot.loader import bot, dp
from bot.db.database import init_db, close_db

from bot.handlers import start
from services.notify import set_bot


# =========================
# STARTUP
# =========================
async def on_startup():
    print("🚀 Initializing database...")
    await init_db()

    print("🤖 Inject bot to services...")
    set_bot(bot)

    print("✅ Bot is running...")


# =========================
# SHUTDOWN
# =========================
async def on_shutdown():
    print("🛑 Closing database...")
    await close_db()

    print("👋 Bot stopped")


# =========================
# MAIN
# =========================
async def main():
    dp.include_router(start.router)

    await on_startup()

    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


# =========================
# RUN
# =========================
if __name__ == "__main__":
    asyncio.run(main())
