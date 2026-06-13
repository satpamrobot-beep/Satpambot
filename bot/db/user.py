import hashlib
from bot.db.database import get_pool


# =========================
# FINGERPRINT (ANTI CLONE BASIC)
# =========================
def make_fingerprint(user):
    """
    Simple fingerprint based on Telegram identity.
    (NOT real device fingerprint, but useful for tracking duplicates)
    """
    raw = f"{user.id}:{user.username}:{user.full_name}"
    return hashlib.sha256(raw.encode()).hexdigest()


# =========================
# SAVE USER (UPSERT SAFE)
# =========================
async def save_user(user, ip_hash: str | None = None):
    """
    Save or update user data safely.
    - prevents duplicate insert
    - updates username + tracking info
    """

    try:
        pool = get_pool()
        fingerprint = make_fingerprint(user)

        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (
                    user_id,
                    username,
                    device_tag,
                    ip_hash,
                    created_at,
                    updated_at
                )
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    device_tag = EXCLUDED.device_tag,
                    ip_hash = COALESCE(EXCLUDED.ip_hash, users.ip_hash),
                    updated_at = NOW()
            """,
            user.id,
            user.username or "hidden",
            fingerprint,
            ip_hash
            )

    except Exception as e:
        print("[SAVE USER ERROR]", e)


# =========================
# GET USER
# =========================
async def get_user(user_id: int):
    """
    Get full user row
    """
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE user_id=$1",
                user_id
            )

    except Exception as e:
        print("[GET USER ERROR]", e)
        return None


# =========================
# UPDATE BALANCE (SAFE)
# =========================
async def update_balance(user_id: int, amount: int):
    """
    Add balance safely (atomic update)
    """
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance, 0) + $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """,
            user_id,
            amount
            )

    except Exception as e:
        print("[UPDATE BALANCE ERROR]", e)


# =========================
# SET BALANCE (OPTIONAL)
# =========================
async def set_balance(user_id: int, amount: int):
    """
    Force set balance
    """
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET balance = $2,
                    updated_at = NOW()
                WHERE user_id = $1
            """,
            user_id,
            amount
            )

    except Exception as e:
        print("[SET BALANCE ERROR]", e)
