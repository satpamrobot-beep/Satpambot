import asyncio
import sys
import os

# =========================
# FIX PATH
# =========================
sys.path.insert(0, os.getcwd())

print("PROJECT ROOT FILES:", os.listdir("."))


from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import BOT_TOKEN
from db.pool import init_db

# =========================
# IMPORT ALL ROUTERS
# =========================
from bot.handlers.start import router as start_router
from bot.handlers.user_callbacks import router as user_router
from bot.handlers.admin_panel import router as admin_router
from bot.handlers.admin_callbacks import router as admin_cb_router


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    # =========================
    # INIT DATABASE
    # =========================
    await init_db()

    # =========================
    # REGISTER ROUTERS (IMPORTANT ORDER)
    # =========================
    dp.include_router(start_router)
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(admin_cb_router)

    print("🔥 BOT STARTED SUCCESSFULLY")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    asyncio.run(main())
