from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================
# ADD MEDIA
# =========================
async def add_media(
    code,
    file_id,
    file_type
):
    try:
        return (
            supabase.table("media")
            .insert({
                "code": code,
                "file_id": file_id,
                "file_type": file_type
            })
            .execute()
        )

    except Exception as e:
        print("[add_media error]", e)
        return None


# =========================
# GET MEDIA
# =========================
async def get_media(code):
    try:
        res = (
            supabase.table("media")
            .select("*")
            .eq("code", code)
            .execute()
        )

        return res.data or []

    except Exception as e:
        print("[get_media error]", e)
        return []
