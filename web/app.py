from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import time

app = FastAPI()

# SIMULATED CACHE / BOT STATE
BOT_STATE = {
    "anti_link": True,
    "anti_spam": True,
    "ai_mode": True
}

analytics = {
    "messages": 0,
    "users": set(),
    "groups": set(),
    "heatmap": {}
}

# =========================
# LOGIN PANEL (simple)
# =========================
@app.get("/", response_class=HTMLResponse)
def login():
    return """
    <h1>🔥 ROSE CLONE DASHBOARD</h1>
    <form action="/dashboard">
        <input placeholder="Username"/>
        <input type="password" placeholder="Password"/>
        <button>Login</button>
    </form>
    """

# =========================
# DASHBOARD CONTROL PANEL
# =========================
@app.get("/dashboard")
def dashboard():
    return {
        "bot_state": BOT_STATE,
        "analytics": analytics
    }

# =========================
# TOGGLE FEATURES LIVE
# =========================
@app.post("/toggle/{feature}")
async def toggle(feature: str):
    BOT_STATE[feature] = not BOT_STATE.get(feature, False)
    return {"feature": feature, "value": BOT_STATE[feature]}

# =========================
# LIVE ANALYTICS UPDATE
# =========================
@app.post("/event")
async def event(request: Request):
    data = await request.json()

    analytics["messages"] += 1
    analytics["users"].add(data["user_id"])
    analytics["groups"].add(data["chat_id"])

    loc = data.get("location", "unknown")
    analytics["heatmap"][loc] = analytics["heatmap"].get(loc, 0) + 1

    return {"status": "ok"}
