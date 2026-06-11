from db.pool import get_pool


async def add_media(code, file_id, file_type):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO media (code, file_id, file_type)
            VALUES ($1, $2, $3)
        """, code, file_id, file_type)


async def get_media(code):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM media WHERE code = $1
        """, code)
