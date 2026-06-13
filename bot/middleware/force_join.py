from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from bot.handlers.start import force_join, join_kb


class ForceJoinMiddleware(BaseMiddleware):

    async def __call__(self, handler: Callable, event: Any, data: Dict[str, Any]):

        bot = data.get("bot")
        user = getattr(event, "from_user", None)

        if not bot or not user:
            return await handler(event, data)

        ok = await force_join(bot, user.id)

        if not ok:

            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Kamu harus join channel & group dulu",
                    reply_markup=join_kb()
                )
                return

            if isinstance(event, CallbackQuery):
                await event.answer("❌ Wajib join dulu", show_alert=True)
                return

            return

        return await handler(event, data)
