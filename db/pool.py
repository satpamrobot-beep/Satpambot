import asyncpg
import os

pool = None


async def init_db():
    global pool

    pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL"),
        min_size=1,
        max_size=10
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
