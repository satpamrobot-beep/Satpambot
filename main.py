import asyncio
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import BOT_TOKEN
from db.pool import init_db
from bot.router import router


# =========================
# FIX PATH (WAJIB PALING ATAS)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)


async def main():
    # =========================
    # INIT BOT (FIX AIogram 3.22)
    # =========================
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    # =========================
    # INIT DATABASE
    # =========================
    try:
        await init_db()
        print("✅ DATABASE CONNECTED")
    except Exception as e:
        print("❌ DATABASE ERROR:", repr(e))
        return

    # =========================
    # REGISTER ROUTER
    # =========================
    dp.include_router(router)

    print("🔥 BOT STARTED")

    # =========================
    # START POLLING
    # =========================
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print("❌ BOT CRASH:", repr(e))
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 STOPPED MANUALLY")
    except Exception as e:
        print("❌ FATAL ERROR:", repr(e))
