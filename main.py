import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from db.pool import init_db
from bot.router import router


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    await init_db()

    dp.include_router(router)

    print("🔥 BOT RUNNING")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
