from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# =========================
# ADD USER
# =========================
async def add_user(user_id: int, username: str = None, first_name: str = None):
    try:
        supabase.table("users").upsert({
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "balance": 0
        }).execute()
    except Exception as e:
        print("[add_user error]", e)


# =========================
# GET BALANCE
# =========================
async def get_balance(user_id: int):
    try:
        res = (
            supabase.table("users")
            .select("balance")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not res.data:
            return 0, 0

        balance = res.data[0].get("balance", 0)
        return balance, 0

    except Exception as e:
        print("[get_balance error]", e)
        return 0, 0


# =========================
# GET USER BALANCE
# =========================
async def get_user_balance(user_id: int):
    balance, _ = await get_balance(user_id)
    return balance
