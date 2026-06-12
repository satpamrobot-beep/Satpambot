import asyncpg
import os

pool = None


# ================= INIT =================

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
        statement_cache_size=0  # 🔥 FIX PGBouncer
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


# ================= WRAPPER DB =================

class Database:
    async def execute(self, query, *args):
        async with get_pool().acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchrow(self, query, *args):
        async with get_pool().acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query, *args):
        async with get_pool().acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchval(self, query, *args):
        async with get_pool().acquire() as conn:
            return await conn.fetchval(query, *args)


# 🔥 INI YANG DIPAKE DI SELURUH PROJECT
DB = Database()
