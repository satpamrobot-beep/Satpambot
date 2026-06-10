import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

BAYARGG_API_KEY = os.getenv("BAYARGG_API_KEY")
BAYARGG_SECRET = os.getenv("BAYARGG_SECRET", "SECRET_KAMU")

BAYARGG_BASE_URL = "https://www.bayar.gg"

ADMINS = {
    int(x)
    for x in os.getenv("ADMINS", "").split(",")
    if x.strip().isdigit()
}

FORCE_CHANNEL = int(os.getenv("FORCE_CHANNEL", "-1003712587847"))
FORCE_CHANNEL_LINK = os.getenv("FORCE_CHANNEL_LINK")

MIN_WITHDRAW = 50000
MAX_WITHDRAW = 500000

OPEN_HOUR = 9
CLOSE_HOUR = 20

MAX_MEDIA = 100
MAX_SIZE = 2 * 1024 * 1024 * 1024
