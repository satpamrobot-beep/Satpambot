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

        if is_maintenance():

            # Message
            if isinstance(event, Message):
                await event.answer(
                    "⚙️ Bot sedang maintenance"
                )
                return

            # Callback
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "Maintenance aktif",
                    show_alert=True
                )
                return

        return await handler(event, data)
