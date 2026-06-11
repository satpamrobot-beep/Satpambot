from bot.services.cache import get_join, set_join

CHANNEL_ID = -1003712587847
GROUP_ID = -1003920865154


async def is_joined(bot, user_id: int) -> bool:
    cached = get_join(user_id)
    if cached is not None:
        return cached

    try:
        ch = await bot.get_chat_member(CHANNEL_ID, user_id)
        gr = await bot.get_chat_member(GROUP_ID, user_id)

        result = (
            ch.status in ("member", "administrator", "creator")
            and gr.status in ("member", "administrator", "creator")
        )

        set_join(user_id, result)
        return result

    except:
        set_join(user_id, False)
        return False
