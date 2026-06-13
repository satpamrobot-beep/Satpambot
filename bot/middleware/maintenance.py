from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from bot.state.admin_state import is_maintenance


class MaintenanceMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ):

        # =========================
        # GLOBAL MAINTENANCE BLOCK
        # =========================
        if is_maintenance():

            # MESSAGE BLOCK
            if isinstance(event, Message):
                await event.answer("⚙️ Bot sedang maintenance")
                return  # STOP TOTAL

            # CALLBACK BLOCK
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "⚙️ Maintenance aktif",
                    show_alert=True
                )
                return  # STOP TOTAL

            # BLOCK ALL OTHER UPDATES TOO
            return

        # =========================
        # NORMAL FLOW
        # =========================
        return await handler(event, data)
