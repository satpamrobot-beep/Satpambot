from db.supabase import supabase


def add_user(user_id, username=None, full_name=None):
    return supabase.table("users").upsert({
        "user_id": user_id,
        "username": username,
        "full_name": full_name
    }).execute()


def get_user_balance(user_id: int):
    res = supabase.table("users").select("balance").eq("user_id", user_id).single().execute()
    return res.data["balance"] if res.data else 0
