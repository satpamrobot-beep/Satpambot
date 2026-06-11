import asyncpg
import os

pool = None


async def init_db():
    global pool

    DATABASE_URL = os.getenv("DATABASE_URL")

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL belum diisi di environment")

    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=60,
        statement_cache_size=0  # 🔥 FIX PGBouncer ERROR
    )

    print("✅ POOLER CONNECTED")


def get_pool():
    if pool is None:
        raise RuntimeError("DB belum init. Jalankan init_db() dulu")
    return pool


async def close_db():
    global pool

    if pool:
        await pool.close()
        pool = None
        print("🔒 POOL CLOSED")
