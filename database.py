import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

pool = None


async def init_db():
    global pool

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10
    )

    print("✅ Supabase Pooler Connected")


def get_pool():
    return pool
