from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Any

from bot.state.admin_state import is_maintenance


class MaintenanceMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict
    ):

        # cek maintenance
        if is_maintenance():

            # allow admin bypass (optional)
            user = data.get("event_from_user")

            if user and user.id == int(data.get("admin_id", 0)):
                return await handler(event, data)

            # handle message
            if isinstance(event, Message):
                await event.answer(
                    "⚙️ Bot sedang maintenance\nSilakan coba lagi nanti"
                )
                return

            # handle callback
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "Bot maintenance",
                    show_alert=True
                )
                return

        return await handler(event, data)
