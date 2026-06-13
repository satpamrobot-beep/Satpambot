from fastapi import APIRouter, Request, Header
from bot.db.database import get_pool
from services.notify import send_user_payment

import hmac
import hashlib
import os

router = APIRouter()

SECRET_KEY = os.getenv("BAYARGG_SECRET", "")


# =========================
# VERIFY SIGNATURE
# =========================
def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    if not SECRET_KEY or not signature:
        return False

    expected = hmac.new(
        SECRET_KEY.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# WEBHOOK BAYARGG (MAX LEVEL)
# =========================
@router.post("/webhook/bayargg")
async def bayargg_webhook(
    request: Request,
    x_signature: str = Header(default=None)
):
    try:
        raw = await request.body()

        # parse sekali saja (lebih aman)
        try:
            data = await request.json()
        except:
            return {"ok": False, "error": "invalid json"}

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

        user_id = data.get("customer_id")
        amount = data.get("amount")
        trx_id = data.get("transaction_id")

        if not user_id or not amount or not trx_id:
            return {"ok": False, "error": "invalid payload"}

        user_id = int(user_id)
        amount = int(amount)
        trx_id = str(trx_id)

        pool = get_pool()

        async with pool.acquire() as conn:

            # =========================
            # 3. ANTI DUPLICATE
            # =========================
            exists = await conn.fetchval(
                "SELECT 1 FROM transactions WHERE trx_id=$1",
                trx_id
            )

            if exists:
                return {"ok": True, "message": "already processed"}

            # =========================
            # 4. LOG TRANSACTION
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
        # 6. NOTIFICATION (NON BLOCKING SAFE)
        # =========================
        asyncio.create_task(send_user_payment(user_id, amount))

        return {"ok": True}

    except Exception as e:
        print("[WEBHOOK ERROR]", str(e))
        return {"ok": False, "error": "server error"}
