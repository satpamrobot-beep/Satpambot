from db.pool import get_pool


async def ensure_user(user_id: int, username: str, full_name: str):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO NOTHING;
        """, user_id, username, full_name)


async def get_balance(user_id: int):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT balance_idr, balance_usd
            FROM users
            WHERE user_id = $1
        """, user_id)

        if not row:
            return 0, 0

        return row["balance_idr"], float(row["balance_usd"])


async def add_balance(user_id: int, amount_idr: int = 0, amount_usd: float = 0):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET balance_idr = balance_idr + $1,
                balance_usd = balance_usd + $2
            WHERE user_id = $3
        """, amount_idr, amount_usd, user_id)
