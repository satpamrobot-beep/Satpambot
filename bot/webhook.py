import os
import hmac
import hashlib
from fastapi import FastAPI, Request
from bot.db.database import get_pool

app = FastAPI()

SECRET_KEY = os.getenv("BAYARGG_SECRET", "")

# =========================
# SIMPLE IN-MEMORY CACHE (ANTI DOUBLE PAY)
# =========================
PROCESSED_TX = set()


# =========================
# VERIFY SIGNATURE (ANTI FAKE WEBHOOK LEVEL UP)
# =========================
def verify_signature(payload: str, signature: str) -> bool:
    """
    Kalau BayarGG support signature HMAC,
    ini akan bikin webhook kamu jauh lebih aman.
    """
    if not SECRET_KEY:
        return False

    expected = hmac.new(
        SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature or "")


# =========================
# WEBHOOK ENDPOINT
# =========================
@app.post("/webhook/bayargg")
async def bayargg(req: Request):
    try:
        raw_body = await req.body()
        data = await req.json()

        # =========================
        # BASIC VALIDATION
        # =========================
        if data.get("status") != "PAID":
            return {"ok": False, "reason": "not_paid"}

        user_id = int(data.get("customer_id", 0))
        amount = int(data.get("amount", 0))
        tx_id = str(data.get("transaction_id", ""))

        if not user_id or not amount or not tx_id:
            return {"ok": False, "reason": "invalid_data"}

        # =========================
        # ANTI DUPLICATE PAYMENT
        # =========================
        if tx_id in PROCESSED_TX:
            return {"ok": True, "reason": "duplicate_ignored"}

        # =========================
        # OPTIONAL SIGNATURE CHECK (IF AVAILABLE)
        # =========================
        signature = data.get("signature")
        if signature:
            if not verify_signature(raw_body.decode(), signature):
                return {"ok": False, "reason": "invalid_signature"}

        PROCESSED_TX.add(tx_id)

        # =========================
        # UPDATE BALANCE (SAFE + ATOMIC)
        # =========================
        pool = get_pool()

        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET balance = COALESCE(balance, 0) + $1
                WHERE user_id = $2
            """, amount, user_id)

        print(f"✅ PAYMENT SUCCESS | user={user_id} amount={amount} tx={tx_id}")

        return {
            "ok": True,
            "message": "balance_updated"
        }

    except Exception as e:
        print("❌ WEBHOOK ERROR:", e)
        return {
            "ok": False,
            "error": str(e)
        }
