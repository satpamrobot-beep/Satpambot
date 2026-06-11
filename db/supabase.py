from supabase import create_client
from config import DATABASE_URL, CHANNEL_DB

supabase = create_client(DATABASE_URL, CHANNEL_DB)
