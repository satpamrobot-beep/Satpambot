import os
from dotenv import load_dotenv

load_dotenv()

# =========================
# CORE BOT CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# BOT USERNAME (WAJIB UNTUK BUTTON ADD GROUP)
# =========================
BOT_USERNAME = os.getenv("BOT_USERNAME")


# =========================
# VALIDATION (ANTI CRASH)
# =========================
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN belum di-set!")

if not OWNER_ID:
    raise ValueError("OWNER_ID belum di-set!")

if not BOT_USERNAME:
    raise ValueError("BOT_USERNAME belum di-set! contoh: mybotnamebot")

try:
    OWNER_ID = int(OWNER_ID)
except ValueError:
    raise ValueError("OWNER_ID harus angka (contoh: 123456789)")


# DATABASE optional
if not DATABASE_URL:
    print("⚠️ DATABASE_URL tidak di-set (bot jalan tanpa database)")
