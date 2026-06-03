import asyncpg
from config import DATABASE_URL


class Database:

    def __init__(self):
        self.pool = None

    # =========================
    # CONNECT
    # =========================

    async def connect(self):

        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=15,
            command_timeout=60
        )

        await self.create_tables()

    async def close(self):

        if self.pool:
            await self.pool.close()

    # =========================
    # TABLES
    # =========================

    async def create_tables(self):

        async with self.pool.acquire() as conn:

            await conn.execute("""

            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS groups(
                chat_id BIGINT PRIMARY KEY,
                title TEXT,
                owner_id BIGINT,

                welcome TEXT,
                leave_message TEXT,

                captcha BOOLEAN DEFAULT FALSE,
                anti_spam BOOLEAN DEFAULT FALSE,

                log_channel BIGINT,
                join_request_enabled BOOLEAN DEFAULT FALSE,

                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS bot_admins(
                user_id BIGINT PRIMARY KEY,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS warns(
                chat_id BIGINT,
                user_id BIGINT,
                count INTEGER DEFAULT 0,
                PRIMARY KEY(chat_id,user_id)
            );

            CREATE TABLE IF NOT EXISTS warnings_log(
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                admin_id BIGINT,
                user_id BIGINT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS bans(
                chat_id BIGINT,
                user_id BIGINT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY(chat_id,user_id)
            );

            CREATE TABLE IF NOT EXISTS mutes(
                chat_id BIGINT,
                user_id BIGINT,
                until_time BIGINT,
                PRIMARY KEY(chat_id,user_id)
            );

            CREATE TABLE IF NOT EXISTS notes(
                chat_id BIGINT,
                keyword TEXT,
                content TEXT,
                PRIMARY KEY(chat_id,keyword)
            );

            CREATE TABLE IF NOT EXISTS filters(
                chat_id BIGINT,
                keyword TEXT,
                response TEXT,
                PRIMARY KEY(chat_id,keyword)
            );

            CREATE TABLE IF NOT EXISTS blacklist_words(
                chat_id BIGINT,
                word TEXT,
                PRIMARY KEY(chat_id,word)
            );

            CREATE TABLE IF NOT EXISTS locks(
                chat_id BIGINT,
                lock_name TEXT,
                enabled BOOLEAN DEFAULT FALSE,
                PRIMARY KEY(chat_id,lock_name)
            );

            CREATE TABLE IF NOT EXISTS flood_settings(
                chat_id BIGINT PRIMARY KEY,
                max_messages INTEGER DEFAULT 6,
                interval_seconds INTEGER DEFAULT 10
            );

            CREATE TABLE IF NOT EXISTS greetings(
                chat_id BIGINT PRIMARY KEY,
                welcome_text TEXT,
                goodbye_text TEXT
            );

            CREATE TABLE IF NOT EXISTS join_requests(
                chat_id BIGINT,
                user_id BIGINT,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY(chat_id,user_id)
            );

            CREATE TABLE IF NOT EXISTS join_leave_logs(
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                user_id BIGINT,
                action TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS reports(
                id SERIAL PRIMARY KEY,
                chat_id BIGINT,
                reporter_id BIGINT,
                target_id BIGINT,
                reason TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS custom_commands(
                chat_id BIGINT,
                command TEXT,
                response TEXT,
                PRIMARY KEY(chat_id,command)
            );

            CREATE TABLE IF NOT EXISTS broadcast_logs(
                id SERIAL PRIMARY KEY,
                total_sent INTEGER,
                failed INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_warns
            ON warns(chat_id,user_id);

            CREATE INDEX IF NOT EXISTS idx_reports
            ON reports(chat_id);

            CREATE INDEX IF NOT EXISTS idx_join_logs
            ON join_leave_logs(chat_id);

            """)

    # =========================
    # USERS
    # =========================

    async def add_user(self, user_id):

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO users(user_id)
                VALUES($1)

                ON CONFLICT(user_id)
                DO NOTHING
                """,
                user_id
            )

    async def count_users(self):

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                "SELECT COUNT(*) total FROM users"
            )

            return row["total"]

    # =========================
    # GROUPS
    # =========================

    async def add_group(
        self,
        chat_id,
        title,
        owner_id
    ):

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO groups(
                    chat_id,
                    title,
                    owner_id
                )

                VALUES($1,$2,$3)

                ON CONFLICT(chat_id)

                DO UPDATE SET
                title=EXCLUDED.title,
                owner_id=EXCLUDED.owner_id
                """,
                chat_id,
                title,
                owner_id
            )

    async def get_group(self, chat_id):

        async with self.pool.acquire() as conn:

            return await conn.fetchrow(
                """
                SELECT *
                FROM groups
                WHERE chat_id=$1
                """,
                chat_id
            )

    async def count_groups(self):

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                "SELECT COUNT(*) total FROM groups"
            )

            return row["total"]

    # =========================
    # WARNS
    # =========================

    async def add_warn(
        self,
        chat_id,
        user_id
    ):

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO warns(
                    chat_id,
                    user_id,
                    count
                )

                VALUES($1,$2,1)

                ON CONFLICT(chat_id,user_id)

                DO UPDATE SET
                count = warns.count + 1
                """,
                chat_id,
                user_id
            )

    async def get_warn(
        self,
        chat_id,
        user_id
    ):

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT count
                FROM warns
                WHERE chat_id=$1
                AND user_id=$2
                """,
                chat_id,
                user_id
            )

            return row["count"] if row else 0

    async def reset_warn(
        self,
        chat_id,
        user_id
    ):

        async with self.pool.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM warns
                WHERE chat_id=$1
                AND user_id=$2
                """,
                chat_id,
                user_id
            )

    # =========================
    # BOT ADMINS
    # =========================

    async def is_bot_admin(
        self,
        user_id
    ):

        async with self.pool.acquire() as conn:

            row = await conn.fetchrow(
                """
                SELECT user_id
                FROM bot_admins
                WHERE user_id=$1
                """,
                user_id
            )

            return bool(row)


db = Database()
