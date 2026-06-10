import asyncpg
from core.config import DATABASE_URL

db_pool = None

async def init_db():
    global db_pool

    db_pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30,
        ssl="require"
    )

    return db_pool
