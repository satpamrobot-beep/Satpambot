import asyncio
import uvicorn

from fastapi import FastAPI

from aiogram import Dispatcher
from bot.loader import bot, dp

from bot.db.database import init_db, close_db
from bot.handlers import start
from services.notify import set_bot

# =========================
# FASTAPI APP
# =========================
app = FastAPI()


# =========================
# INCLUDE WEBHOOK ROUTE
# =========================
from bot.webhook import bayargg_webhook
app.include_router(bayargg_webhook.router if hasattr(bayargg_webhook, "router") else bayargg_webhook)


# =========================
# BOT STARTUP
# =========================
async def on_startup():
    await init_db()
    set_bot(bot)
    print("🤖 Bot ready")


# =========================
# BOT TASK
# =========================
async def start_bot():
    dp.include_router(start.router)
    await dp.start_polling(bot)


# =========================
# FASTAPI RUNNER
# =========================
def start_api():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    return server.serve()


# =========================
# MAIN COMBINED RUNNER
# =========================
async def main():
    await on_startup()

    # jalanin 2 service bareng
    await asyncio.gather(
        start_bot(),
        start_api()
    )


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    asyncio.run(main())
