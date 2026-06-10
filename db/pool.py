import asyncpg
import os

DB_POOL = None


async def init_db():
    global DB_POOL

    DB_POOL = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=1,
        max_size=10
    )

    async with DB_POOL.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance_idr BIGINT DEFAULT 0,
            balance_usd NUMERIC DEFAULT 0
        );
        """)


async def get_pool():
    return DB_POOL
