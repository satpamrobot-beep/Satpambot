from db.pool import get_pool


# =========================
# ADD MEDIA
# =========================
async def add_media(
    code: str,
    file_id: str,
    file_type: str
):
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO media (
                    code,
                    file_id,
                    file_type
                )
                VALUES ($1, $2, $3)
                """,
                code,
                file_id,
                file_type
            )

        return True

    except Exception as e:
        print("[add_media error]", e)
        return False


# =========================
# GET MEDIA
# =========================
async def get_media(code: str):
    try:
        pool = get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM media
                WHERE code = $1
                ORDER BY id ASC
                """,
                code
            )

        return [dict(row) for row in rows]

    except Exception as e:
        print("[get_media error]", e)
        return []
