from db.pool import get_pool


# =========================
# CREATE USER IF NOT EXISTS
# =========================
async def ensure_user(user_id: int, username: str, full_name: str):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users (user_id, username, full_name)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id) DO NOTHING;
        """, user_id, username, full_name)


# =========================
# GET BALANCE
# =========================
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


# =========================
# ADD BALANCE (IDR)
# =========================
async def add_balance_idr(user_id: int, amount: int):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users
        SET balance_idr = balance_idr + $1
        WHERE user_id = $2
        """, amount, user_id)


# =========================
# SUBTRACT BALANCE (IDR)
# =========================
async def sub_balance_idr(user_id: int, amount: int):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute("""
        UPDATE users
        SET balance_idr = GREATEST(balance_idr - $1, 0)
        WHERE user_id = $2
        """, amount, user_id)
