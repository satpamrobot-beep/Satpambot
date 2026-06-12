from aiogram import Router

router = Router()

# =========================
# IMPORT HANDLERS
# =========================
from handlers.start import router as start_router
from bot.handlers.upfile import router as upfile_router
from bot.handlers.getfile import router as getfile_router
from bot.handlers.about import router as about_router
from handlers.callbacks import router as cb_router
# =========================
# INCLUDE ROUTERS
# =========================
router.include_router(start_router)
router.include_router(upfile_router)
router.include_router(getfile_router)
router.include_router(about_router)
router.include_router(cb_router)
