import os
import hmac
import hashlib
from fastapi import FastAPI, Request, Header

from bot.db.database import get_pool

app = FastAPI()

SECRET_KEY = os.getenv("BAYARGG_SECRET", "")


# =========================
# VERIFY SIGNATURE
# =========================
def verify_signature(raw_body: bytes, signature: str | None):
    if not SECRET_KEY:
        return False

    expected = hmac.new(
        SECRET_KEY.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature or "")


# =========================
# SEND NOTIFICATION (OPTIONAL TELEGRAM)
# =========================
async def send_telegram(bot_pool, user_id: int, amount: int):
    try:
        async with bot_pool.acquire() as conn:
            await conn.execute(
                "SELECT 1"
            )
        # kalau kamu mau, nanti kita sambungkan ke aiogram bot instance
    except:
        pass


# =========================
# WEBHOOK BAYARGG (PRODUCTION LEVEL)
# =========================
@app.post("/webhook/bayargg")
async def bayargg_webhook(
    request: Request,
    x_signature: str = Header(default=None)
):
    try:
        raw = await request.body()
        data = await request.json()

        # =========================
        # 1. VERIFY SIGNATURE
        # =========================
        if not verify_signature(raw, x_signature):
            return {"ok": False, "error": "invalid signature"}

        # =========================
        # 2. VALIDATE PAYMENT
        # =========================
        if data.get("status") != "PAID":
            return {"ok": False}

        user_id = int(data.get("customer_id", 0))
        amount = int(data.get("amount", 0))
        trx_id = str(data.get("transaction_id", ""))

        if not user_id or not amount or not trx_id:
            return {"ok": False, "error": "invalid payload"}

        pool = get_pool()

        async with pool.acquire() as conn:

            # =========================
            # 3. CHECK DUPLICATE (DB LEVEL - REAL PROTECTION)
            # =========================
            exists = await conn.fetchval(
                "SELECT 1 FROM transactions WHERE trx_id=$1",
                trx_id
            )

            if exists:
                return {"ok": True, "message": "already processed"}

            # =========================
            # 4. INSERT TRANSACTION LOG
            # =========================
            await conn.execute("""
                INSERT INTO transactions (trx_id, user_id, amount, status)
                VALUES ($1, $2, $3, 'SUCCESS')
            """, trx_id, user_id, amount)

            # =========================
            # 5. UPDATE BALANCE (ATOMIC)
            # =========================
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance,0) + $1
                WHERE user_id=$2
            """, amount, user_id)

        return {"ok": True}

    except Exception as e:
        print("[WEBHOOK ERROR]", e)
        return {"ok": False, "error": "server error"}
