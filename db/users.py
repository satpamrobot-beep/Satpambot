from db.pool import get_pool


async def add_user(user_id: int, username: str = None, first_name: str = None):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, username, first_name)


async def get_balance(user_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT balance FROM users WHERE user_id = $1
        """, user_id)

        if not row:
            return 0, 0

        balance = row["balance"]
        return balance, 0
