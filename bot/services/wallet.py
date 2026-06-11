from db.users import get_balance as db_get_balance
from bot.services.cache import get_user, set_user


async def get_balance(user_id: int):
    cached = get_user(user_id)
    if cached:
        return cached["idr"], cached["usd"]

    idr, usd = await db_get_balance(user_id)

    set_user(user_id, {
        "idr": idr,
        "usd": usd
    })

    return idr, usd
