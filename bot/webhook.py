from fastapi import APIRouter, Request, Header
from bot.db.database import get_pool
from services.notify import notify_payment, send_group

import hmac
import hashlib
import os
import asyncio
import time

router = APIRouter()

SECRET_KEY = os.getenv("BAYARGG_SECRET", "")


# =========================
# VERIFY SIGNATURE (SECURE)
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
# SIMPLE IN-MEMORY DEDUP CACHE (FAST LAYER)
# =========================
PROCESSED_CACHE = {}
CACHE_TTL = 300  # 5 menit


def is_recent_duplicate(trx_id: str) -> bool:
    now = time.time()

    # cleanup old cache
    for k in list(PROCESSED_CACHE.keys()):
        if now - PROCESSED_CACHE[k] > CACHE_TTL:
            del PROCESSED_CACHE[k]

    if trx_id in PROCESSED_CACHE:
        return True

    PROCESSED_CACHE[trx_id] = now
    return False


# =========================
# WEBHOOK BAYARGG (MAX PRO)
# =========================
@router.post("/webhook/bayargg")
async def bayargg_webhook(
    request: Request,
    x_signature: str = Header(default=None)
):
    try:
        raw = await request.body()

        # parse JSON
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
        # 2. STATUS CHECK
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

        if amount <= 0:
            return {"ok": False, "error": "invalid amount"}

        # =========================
        # 3. FAST DUPLICATE CHECK (CACHE LAYER)
        # =========================
        if is_recent_duplicate(trx_id):
            return {"ok": True, "message": "cached duplicate ignored"}

        pool = get_pool()

        async with pool.acquire() as conn:

            # =========================
            # 4. HARD DUPLICATE CHECK (DB LAYER)
            # =========================
            inserted = await conn.fetchval("""
                INSERT INTO transactions (trx_id, user_id, amount, status)
                VALUES ($1, $2, $3, 'SUCCESS')
                ON CONFLICT (trx_id) DO NOTHING
                RETURNING trx_id
            """, trx_id, user_id, amount)

            if not inserted:
                return {"ok": True, "message": "db duplicate ignored"}

            # =========================
            # 5. UPDATE BALANCE (ATOMIC SAFE)
            # =========================
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance,0) + $1
                WHERE user_id=$2
            """, amount, user_id)

        # =========================
        # 6. NOTIFY (NON-BLOCKING PARALLEL)
        # =========================
        asyncio.create_task(notify_payment(user_id, amount, trx_id))

        asyncio.create_task(send_group(
            "💸 <b>PAYMENT SUCCESS</b>\n"
            f"👤 User: <code>{user_id}</code>\n"
            f"💰 Amount: Rp {amount:,.0f}\n"
            f"🧾 TRX: <code>{trx_id}</code>"
        ))

        return {
            "ok": True,
            "status": "processed",
            "user_id": user_id,
            "amount": amount
        }

    except Exception as e:
        print("[WEBHOOK ERROR]", str(e))
        return {"ok": False, "error": "server error"}
