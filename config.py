import os
from dotenv import load_dotenv

load_dotenv()


# =========================
# CORE BOT
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


# =========================
# OWNER & ADMINS
# =========================
OWNER_ID = int(os.getenv("OWNER_ID") or 0)

ADMINS = {
    int(x)
    for x in os.getenv("ADMINS", "").split(",")
    if x.strip().isdigit()
}


# =========================
# FORCE JOIN CONFIG
# =========================
FORCE_CHANNEL = int(os.getenv("FORCE_CHANNEL") or 0)
GROUP_ID = int(os.getenv("GROUP_ID") or 0)

UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "")
NOTIFICATION_CHANNEL = int(os.getenv("NOTIFICATION_CHANNEL") or 0)


# =========================
# VIP
# =========================
VIP_LINK = os.getenv("VIP_LINK", "")
