from db.pool import get_pool


async def create_upload(code, owner_id, access_type, price, visibility):
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO uploads (code, owner_id, access_type, price, visibility)
            VALUES ($1, $2, $3, $4, $5)
        """, code, owner_id, access_type, price, visibility)


async def get_upload(code):
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            SELECT * FROM uploads WHERE code = $1
        """, code)
