import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN

# =========================
# HANDLERS IMPORT
# =========================
from handlers import admin, moderation, welcome, start, help
from handlers.panel import router as panel_router  # 🔥 PANEL TAMBAHAN

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)


# =========================
# MAIN FUNCTION
# =========================
async def main():

    print("🚀 Bot starting...")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # =========================
    # REGISTER ROUTERS
    # =========================
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(moderation.router)
    dp.include_router(welcome.router)
    dp.include_router(help.router)

    # 🔥 PANEL SYSTEM
    dp.include_router(panel_router)

    print("🤖 Bot running...")

    await dp.start_polling(bot)


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ BOT ERROR:", e)
