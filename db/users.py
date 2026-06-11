from db.pool import get_pool


# =========================
# ADD USER
# =========================
async def add_user(
    user_id: int,
    username: str = None,
    first_name: str = None
):
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    username,
                    first_name,
                    balance
                )
                VALUES ($1, $2, $3, 0)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
                """,
                user_id,
                username,
                first_name
            )

    except Exception as e:
        print("[add_user error]", e)


# =========================
# GET BALANCE
# =========================
async def get_balance(user_id: int):
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT balance
                FROM users
                WHERE user_id = $1
                LIMIT 1
                """,
                user_id
            )

        if not row:
            return 0, 0

        return row["balance"], 0

    except Exception as e:
        print("[get_balance error]", e)
        return 0, 0


# =========================
# GET USER BALANCE
# =========================
async def get_user_balance(user_id: int):
    balance, _ = await get_balance(user_id)
    return balance
