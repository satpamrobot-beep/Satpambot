from fastapi import APIRouter, Request, Header
from bot.db.database import get_pool

from services.notify import notify_payment

import hmac
import hashlib
import os
import asyncio

router = APIRouter()

SECRET_KEY = os.getenv("BAYARGG_SECRET", "")


# =========================
# VERIFY SIGNATURE
# =========================
def verify_signature(raw: bytes, signature: str | None) -> bool:
    if not SECRET_KEY or not signature:
        return False

    expected = hmac.new(
        SECRET_KEY.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


# =========================
# WEBHOOK BAYARGG FULL PRO
# =========================
@router.post("/webhook/bayargg")
async def bayargg_webhook(
    request: Request,
    x_signature: str = Header(default=None)
):
    try:
        raw = await request.body()

        try:
            data = await request.json()
        except:
            return {"ok": False}

        # 1. SECURITY
        if not verify_signature(raw, x_signature):
            return {"ok": False, "error": "invalid signature"}

        # 2. STATUS CHECK
        if data.get("status") != "PAID":
            return {"ok": True}

        user_id = int(data.get("customer_id", 0))
        amount = int(data.get("amount", 0))
        trx_id = str(data.get("transaction_id", ""))

        if not user_id or not amount or not trx_id:
            return {"ok": False}

        if amount <= 0:
            return {"ok": False}

        pool = get_pool()

        async with pool.acquire() as conn:

            # 3. ANTI DUPLICATE (HARD)
            inserted = await conn.fetchval("""
                INSERT INTO transactions (trx_id, user_id, amount, status)
                VALUES ($1, $2, $3, 'SUCCESS')
                ON CONFLICT (trx_id) DO NOTHING
                RETURNING trx_id
            """, trx_id, user_id, amount)

            if not inserted:
                return {"ok": True}

            # 4. UPDATE BALANCE
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance,0) + $1
                WHERE user_id=$2
            """, amount, user_id)

        # 5. NOTIFY (NON BLOCKING)
        asyncio.create_task(
            notify_payment(user_id, amount, trx_id)
        )

        return {"ok": True}

    except Exception as e:
        print("[WEBHOOK ERROR]", e)
        return {"ok": False}
