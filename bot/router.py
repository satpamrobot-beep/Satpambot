from aiogram import Router

from bot.handlers.start import router as start_router
from bot.handlers.admin import router as admin_router
from bot.handlers.callback import router as callback_router

router = Router()

router.include_router(start_router)
router.include_router(admin_router)
router.include_router(callback_router)
