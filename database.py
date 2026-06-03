import asyncpg
from config import DATABASE_URL

class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL)

    # ================= USERS =================
    async def add_user(self, user_id):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users(user_id)
                VALUES($1)
                ON CONFLICT DO NOTHING
            """, user_id)

    # ================= GROUP SETTINGS =================
    async def set_welcome(self, chat_id, text):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO groups(chat_id, welcome)
                VALUES($1, $2)
                ON CONFLICT (chat_id)
                DO UPDATE SET welcome=$2
            """, chat_id, text)

    async def get_welcome(self, chat_id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT welcome FROM groups WHERE chat_id=$1",
                chat_id
            )
            return row["welcome"] if row else None

db = Database()
