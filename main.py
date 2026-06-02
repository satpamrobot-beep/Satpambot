import requests
from telegram.ext import Application, MessageHandler, filters

API_URL = "https://your-railway-url.up.railway.app"

# =========================
# SEND EVENT KE DASHBOARD
# =========================
def send_event(update):
    try:
        requests.post(API_URL + "/event", json={
            "user_id": update.effective_user.id,
            "chat_id": update.effective_chat.id,
            "location": "id"
        })
    except:
        pass

# =========================
# SECURITY + AI HOOK
# =========================
async def guard(update, context):
    if not update.message:
        return

    send_event(update)

    text = (update.message.text or "").lower()

    # ambil config dari dashboard
    try:
        config = requests.get(API_URL + "/dashboard").json()["bot_state"]
    except:
        config = {}

    # anti link LIVE CONTROL
    if config.get("anti_link") and "http" in text:
        await update.message.delete()
        return

    # anti spam simple
    if config.get("anti_spam"):
        if len(text) > 200:
            await update.message.delete()
            return

app = Application.builder().token("TOKEN").build()
app.add_handler(MessageHandler(filters.ALL, guard))
app.run_polling()
