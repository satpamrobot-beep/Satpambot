from db.pool import get_pool


# =========================
# CREATE UPLOAD
# =========================
async def create_upload(
    code: str,
    owner_id: int,
    access_type: str = "free",
    price: int = 0,
    visibility: str = "public"
):
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO uploads (
                    code,
                    owner_id,
                    access_type,
                    price,
                    visibility
                )
                VALUES ($1, $2, $3, $4, $5)
                """,
                code,
                owner_id,
                access_type,
                price,
                visibility
            )

        return True

    except Exception as e:
        print("[create_upload error]", e)
        return False


# =========================
# GET UPLOAD
# =========================
async def get_upload(code: str):
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT *
                FROM uploads
                WHERE code = $1
                LIMIT 1
                """,
                code
            )

        return dict(row) if row else None

    except Exception as e:
        print("[get_upload error]", e)
        return None


# =========================
# CHECK UPLOAD EXISTS
# =========================
async def upload_exists(code: str) -> bool:
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM uploads
                WHERE code = $1
                LIMIT 1
                """,
                code
            )

        return row is not None

    except Exception as e:
        print("[upload_exists error]", e)
        return False
