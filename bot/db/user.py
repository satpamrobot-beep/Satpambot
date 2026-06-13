from bot.db.database import get_pool

async def save_user(user):
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                user.id,
                user.username
            )
    except:
        pass
