import os
from fastapi import FastAPI, Request
from bot.db.database import get_pool

app = FastAPI()

SECRET_KEY = os.getenv("BAYARGG_SECRET")


@app.post("/webhook/bayargg")
async def bayargg(req: Request):
    try:
        data = await req.json()

        # cek status pembayaran
        if data.get("status") != "PAID":
            return {"ok": False}

        # cek secret (ANTI FAKE)
        if data.get("secret") != SECRET_KEY:
            return {"ok": False}

        user_id = int(data["customer_id"])
        amount = int(data["amount"])

        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance, 0) + $1
                WHERE user_id = $2
            """, amount, user_id)

        return {"ok": True}

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return {"ok": False}
