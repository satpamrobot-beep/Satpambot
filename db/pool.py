import asyncpg
import os

DB_POOL = None


async def init_db():
    global DB_POOL

    DB_POOL = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=1,
        max_size=10,

        # 🔥 FIX PENTING UNTUK PALO / RAILWAY / PGBouncer
        statement_cache_size=0,
        max_cached_statement_lifetime=0,
    )

    async with DB_POOL.acquire() as conn:

        # =========================
        # CREATE TABLE (SAFE)
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            balance_idr BIGINT DEFAULT 0,
            balance_usd NUMERIC DEFAULT 0
        );
        """)

        # =========================
        # SAFE MIGRATION (IDEMPOTENT)
        # =========================
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_idr BIGINT DEFAULT 0;")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS balance_usd NUMERIC DEFAULT 0;")


async def get_pool():
    return DB_POOL
