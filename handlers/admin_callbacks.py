from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()


@router.callback_query(F.data == "adm_stats")
async def stats(call: CallbackQuery):
    await call.message.answer("📊 Stats system")
    await call.answer()


@router.callback_query(F.data == "adm_broadcast")
async def broadcast(call: CallbackQuery):
    await call.message.answer("📢 Broadcast system")
    await call.answer()


@router.callback_query(F.data == "adm_maintenance")
async def maintenance(call: CallbackQuery):
    await call.message.answer("🛠 Maintenance toggle")
    await call.answer()
