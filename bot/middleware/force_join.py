from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any

from bot.handlers.start import force_join, join_kb


class ForceJoinMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable,
        event: Any,
        data: Dict[str, Any]
    ):

        bot = data.get("bot")
        user = getattr(event, "from_user", None)

        if not bot or not user:
            return await handler(event, data)

        # =========================
        # FORCE JOIN CHECK
        # =========================
        ok = await force_join(bot, user.id)

        if not ok:

            # MESSAGE HANDLER
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Kamu harus join channel & group dulu",
                    reply_markup=join_kb()
                )
                return  # STOP TOTAL

            # CALLBACK HANDLER
            if isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Wajib join dulu",
                    show_alert=True
                )

                # optional: jangan biarkan handler lanjut
                return

            return

        # =========================
        # PASS TO NEXT HANDLER
        # =========================
        return await handler(event, data)
