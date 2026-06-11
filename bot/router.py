from aiogram import Router

router = Router()

# =========================
# IMPORT HANDLERS
# =========================
from handlers.start import router as start_router

# =========================
# INCLUDE ROUTERS
# =========================
router.include_router(start_router)
