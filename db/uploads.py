from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# CREATE UPLOAD
# =========================
async def create_upload(
    code,
    owner_id,
    access_type="free",
    price=0,
    visibility="public"
):
    try:
        return (
            supabase.table("uploads")
            .insert({
                "code": code,
                "owner_id": owner_id,
                "access_type": access_type,
                "price": price,
                "visibility": visibility
            })
            .execute()
        )

    except Exception as e:
        print("[create_upload error]", e)
        return None


# =========================
# GET UPLOAD
# =========================
async def get_upload(code):
    try:
        res = (
            supabase.table("uploads")
            .select("*")
            .eq("code", code)
            .limit(1)
            .execute()
        )

        if not res.data:
            return None

        return res.data[0]

    except Exception as e:
        print("[get_upload error]", e)
        return None
