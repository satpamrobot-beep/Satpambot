import os
from dotenv import load_dotenv

load_dotenv()

# BOT
BOT_TOKEN = os.getenv("BOT_TOKEN")

# DATABASE
DATABASE_URL = os.getenv("DATABASE_URL")

# FORCE SUB
CHANNEL_UPDATE = os.getenv("CHANNEL_UPDATE")
GROUP_CHAT = os.getenv("GROUP_CHAT")

# ADMIN
ADMIN_IDS = list(
    map(int, os.getenv("ADMIN_IDS", "").split(","))
    if os.getenv("ADMIN_IDS")
    else []
)

# BAYARGG
BAYARGG_API_KEY = os.getenv("BAYARGG_API_KEY")
BAYARGG_SECRET = os.getenv("BAYARGG_SECRET")
