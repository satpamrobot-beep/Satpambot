from config import FORCE_CHANNEL, GROUP_ID


# =========================
# CHECK JOIN (CHANNEL + GROUP)
# =========================
async def is_joined(bot, user_id: int) -> bool:
    """
    Return True kalau user sudah join CHANNEL + GROUP
    """

    try:
        # cek channel
        ch = await bot.get_chat_member(FORCE_CHANNEL, user_id)

        # cek group
        gr = await bot.get_chat_member(GROUP_ID, user_id)

        # status yang dianggap TIDAK JOIN
        bad_status = ["left", "kicked"]

        if ch.status in bad_status:
            return False

        if gr.status in bad_status:
            return False

        return True

    except Exception:
        # kalau bot belum admin / error telegram API
        return False
