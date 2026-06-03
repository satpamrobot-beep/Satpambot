from config import MAINTENANCE_MODE, MAINTENANCE_TEXT

async def check_maintenance(message):
    if MAINTENANCE_MODE:
        await message.reply(MAINTENANCE_TEXT, parse_mode="HTML")
        return True
    return False
