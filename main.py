import asyncio
import os
import uvicorn

from fastapi import FastAPI

from bot.loader import bot, dp
from bot.db.database import init_db
from bot.handlers import start
from services.notify import set_bot
from bot.web.admin import router as admin_router

# =========================
# FASTAPI APP
# =========================
app = FastAPI()

# =========================
# WEBHOOK ROUTER
# =========================
from bot.webhook import router as bayargg_router
app.include_router(bayargg_router)
app.include_router(admin_router)

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
# FASTAPI RUNNER (RAILWAY SAFE)
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
# MAIN RUNNER
# =========================
async def main():
    await on_startup()

    await asyncio.gather(
        start_bot(),
        start_api()
    )


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    asyncio.run(main())
