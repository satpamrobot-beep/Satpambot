from fastapi import Request, Header
from bot.db.database import get_pool
from services.notify import send_user_payment

import hmac
import hashlib
import os

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
# WEBHOOK BAYARGG (PRO MAX)
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
        # 1. SECURITY CHECK
        # =========================
        if not verify_signature(raw, x_signature):
            return {"ok": False, "error": "invalid signature"}

        # =========================
        # 2. VALIDATE STATUS
        # =========================
        if data.get("status") != "PAID":
            return {"ok": True}

        user_id = int(data.get("customer_id", 0))
        amount = int(data.get("amount", 0))
        trx_id = str(data.get("transaction_id", ""))

        if not user_id or not amount or not trx_id:
            return {"ok": False, "error": "invalid payload"}

        pool = get_pool()

        async with pool.acquire() as conn:

            # =========================
            # 3. ANTI DUPLICATE (DB LEVEL)
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
            # 5. UPDATE BALANCE (ATOMIC SAFE)
            # =========================
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance,0) + $1
                WHERE user_id=$2
            """, amount, user_id)

        # =========================
        # 6. SEND TELEGRAM NOTIFICATION (AFTER DB SUCCESS)
        # =========================
        await send_user_payment(user_id, amount)

        return {"ok": True}

    except Exception as e:
        print("[WEBHOOK ERROR]", e)
        return {"ok": False, "error": "server error"}
