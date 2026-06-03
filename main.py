import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN

from database import db

from handlers import (
    admin,
    moderation,
    welcome,
    start,
    help
)

from handlers.group_events import (
    router as group_events_router
)

from handlers.broadcast import (
    router as broadcast_router
)

from handlers.panel import (
    router as panel_router
)

logging.basicConfig(
    level=logging.INFO
)


async def main():

    await db.connect()

    bot = Bot(
        token=BOT_TOKEN
    )

    dp = Dispatcher()

    # =========================
    # ROUTERS
    # =========================

    dp.include_router(
        start.router
    )

    dp.include_router(
        group_events_router
    )

    dp.include_router(
        admin.router
    )

    dp.include_router(
        moderation.router
    )

    dp.include_router(
        welcome.router
    )

    dp.include_router(
        help.router
    )

    dp.include_router(
        broadcast_router
    )

    dp.include_router(
        panel_router
    )

    print(
        "🤖 Bot running..."
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        await db.close()


if __name__ == "__main__":

    asyncio.run(
        main()
    )
