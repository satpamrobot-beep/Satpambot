import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


# =========================
# INIT DATABASE (FIX SUPABASE POOLER)
# =========================
async def init_db():
    global _pool

    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise RuntimeError("❌ DATABASE_URL tidak ditemukan")

    try:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,

            # =========================
            # POOL SETTINGS (AMAN RAILWAY + SUPABASE)
            # =========================
            min_size=1,
            max_size=5,
            command_timeout=60,

            # 🔥 FIX UTAMA UNTUK POOLEr (PgBouncer)
            statement_cache_size=0,
            max_cached_statement_lifetime=0,
        )

        print("✅ Supabase Pooler Connected")

        return _pool

    except Exception as e:
        print(f"❌ DB INIT ERROR: {e}")
        raise


# =========================
# GET POOL
# =========================
def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("❌ DB belum di init (jalankan init_db dulu)")
    return _pool


# =========================
# CLOSE DB
# =========================
async def close_db():
    global _pool

    if _pool:
        await _pool.close()
        _pool = None
        print("🔒 Database Closed")


# =========================
# HEALTH CHECK (OPSIONAL)
# =========================
async def health_check():
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return True

    except Exception as e:
        print(f"❌ Health Check Failed: {e}")
        return False
