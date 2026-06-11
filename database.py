import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def init_db():
    global _pool

    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL tidak ditemukan."
        )

    try:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=1,
            max_size=10,
            max_inactive_connection_lifetime=300,
            command_timeout=60
        )

        print("✅ Supabase Pooler Connected")

        return _pool

    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        raise


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError(
            "Database belum diinisialisasi. Jalankan await init_db() terlebih dahulu."
        )

    return _pool


async def close_db():
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None

        print("🔒 Database Pool Closed")


async def health_check():
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return True

    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False
