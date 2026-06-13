import os
from fastapi import FastAPI, Request
from bot.db.database import get_pool

app = FastAPI()

SECRET = os.getenv("BAYARGG_SECRET")


# =========================
# WEBHOOK PAYMENT / CODE SOLD
# =========================
@app.post("/webhook/sold")
async def sold(req: Request):
    data = await req.json()

    # validasi simple
    if data.get("status") != "PAID":
        return {"ok": False}

    if data.get("secret") != SECRET:
        return {"ok": False}

    user_id = int(data["user_id"])
    amount = int(data["amount"])

    pool = get_pool()

    async with pool.acquire() as conn:

        # 🔥 AUTO ADD BALANCE
        await conn.execute("""
            UPDATE users
            SET balance = COALESCE(balance,0) + $1
            WHERE user_id=$2
        """, amount, user_id)

    return {"ok": True}
