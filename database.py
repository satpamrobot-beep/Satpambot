import asyncpg
import os

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.Pool | None = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=10
    )
    print("✅ PostgreSQL Pool Connected")


def get_pool():
    return pool
