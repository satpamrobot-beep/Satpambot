import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from bot.router import router


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    # hapus webhook lama jika ada
    await bot.delete_webhook(
        drop_pending_updates=True
    )

    dp = Dispatcher()

    # register router
    dp.include_router(router)

    me = await bot.get_me()

    print(f"🔥 BOT RUNNING: @{me.username}")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 BOT STOPPED")
