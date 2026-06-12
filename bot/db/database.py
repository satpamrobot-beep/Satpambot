import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool

    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL tidak ditemukan")

    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=60
    )

    print("✅ Supabase Pooler Connected")
    return _pool


def get_pool():
    if _pool is None:
        raise RuntimeError("DB belum di init")
    return _pool


async def close_db():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None
