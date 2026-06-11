from config import FORCE_CHANNEL, GROUP_ID


# =========================
# CHECK JOIN (PRODUCTION READY)
# =========================
async def is_joined(bot, user_id: int) -> bool:
    """
    Return True jika user sudah join channel + group
    """

    try:
        ch = await bot.get_chat_member(FORCE_CHANNEL, user_id)
        gr = await bot.get_chat_member(GROUP_ID, user_id)

        # status yang TIDAK VALID JOIN
        bad_status = {"left", "kicked", "restricted"}

        # status yang VALID JOIN
        good_status = {"member", "administrator", "creator"}

        # =========================
        # CHANNEL CHECK
        # =========================
        if ch.status not in good_status:
            return False

        # =========================
        # GROUP CHECK
        # =========================
        if gr.status not in good_status:
            return False

        return True

    except Exception as e:
        print("[JOIN CHECK ERROR]", e)
        return False
