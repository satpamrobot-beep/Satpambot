import asyncio
import os
import uvicorn

from fastapi import FastAPI

from bot.loader import bot, dp
from bot.db.database import init_db

from bot.middleware.maintenance import MaintenanceMiddleware
from bot.web.admin import router as admin_router
from bot.webhook import router as bayargg_router

from services.notify import set_bot
from bot.handlers import start


# =========================
# FASTAPI APP
# =========================
app = FastAPI()

app.include_router(bayargg_router)
app.include_router(admin_router)


# =========================
# BOT STARTUP HOOK
# =========================
async def on_startup():
    await init_db()
    set_bot(bot)

    # ROUTER ONLY ONCE
    dp.include_router(start.router)

    # MIDDLEWARE ORDER (IMPORTANT)
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())


    print("🤖 Bot ready")

# =========================
# BOT RUNNER
# =========================
async def start_bot():
    await on_startup()

    print("🤖 Bot polling started")

    await dp.start_polling(bot)


# =========================
# FASTAPI RUNNER
# =========================
async def start_api():
    PORT = int(os.getenv("PORT", 8000))

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )

    server = uvicorn.Server(config)
    await server.serve()


# =========================
# MAIN
# =========================
async def main():
    await asyncio.gather(
        start_bot(),
        start_api()
    )


if __name__ == "__main__":
    asyncio.run(main())
