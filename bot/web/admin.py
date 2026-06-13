from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import os
import json
import asyncio

from bot.db.database import get_pool
from bot.state.admin_state import set_maintenance, is_maintenance, push_log
from services.notify import send_group, broadcast

router = APIRouter()

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")


# =========================
# AUTH
# =========================
def check_token(token: str) -> bool:
    return token == ADMIN_TOKEN


# =========================
# WEBSOCKET MANAGER
# =========================
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(data))
            except:
                dead.append(ws)

        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()


# =========================
# WEBSOCKET ENDPOINT
# =========================
@router.websocket("/admin/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)

    try:
        while True:
            # keep alive / ignore client messages
            await ws.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(ws)


# =========================
# PUSH STATS (REALTIME ENGINE)
# =========================
async def push_stats():
    pool = get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        trx = await conn.fetchval("SELECT COUNT(*) FROM transactions") or 0
        balance = await conn.fetchval("SELECT COALESCE(SUM(balance),0) FROM users") or 0

    await manager.broadcast({
        "type": "stats",
        "users": users,
        "trx": trx,
        "balance": int(balance)
    })


# =========================
# PUSH LOG
# =========================
async def push_live_log(message: str):
    push_log(message)

    await manager.broadcast({
        "type": "log",
        "data": list(reversed(getattr(push_log, "buffer", [])))
    })


# =========================
# DASHBOARD UI
# =========================
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(token: str = Query(default="")):

    if not check_token(token):
        return HTMLResponse("403 Forbidden", status_code=403)

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>ADMIN PRO DASHBOARD</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<style>
body {{
    margin:0;
    font-family:Arial;
    background:#0a0f1a;
    color:#e5e7eb;
    display:flex;
    height:100vh;
}}

.sidebar {{
    width:270px;
    background:#111827;
    padding:10px;
    overflow:auto;
}}

.main {{
    flex:1;
    padding:12px;
    overflow:auto;
}}

.card {{
    background:#1f2937;
    padding:10px;
    margin:6px 0;
    border-radius:10px;
    cursor:pointer;
}}

.box {{
    display:inline-block;
    background:#1f2937;
    padding:10px;
    margin:5px;
    border-radius:10px;
    width:140px;
}}

button {{
    padding:8px;
    margin:4px;
    border:none;
    border-radius:8px;
    cursor:pointer;
}}

textarea {{
    width:100%;
    height:70px;
    border-radius:8px;
}}

.log {{
    background:#0f172a;
    height:180px;
    overflow:auto;
    padding:10px;
    font-size:12px;
}}
</style>
</head>

<body>

<div class="sidebar">
<h3>👥 USERS</h3>
<div id="users"></div>
</div>

<div class="main">

<h2>📊 REALTIME ADMIN</h2>

<div class="box">Users<br><b id="u">0</b></div>
<div class="box">Trx<br><b id="t">0</b></div>
<div class="box">Balance<br><b id="b">0</b></div>

<canvas id="chart"></canvas>

<hr>

<div id="detail" class="card">Select user</div>

<hr>

<h3>📢 BROADCAST</h3>
<textarea id="msg"></textarea>
<button onclick="broadcastMsg()">Send</button>

<hr>

<h3>⚙️ MAINTENANCE</h3>
<button onclick="maint(true)">ON</button>
<button onclick="maint(false)">OFF</button>

<hr>

<h3>📡 LIVE LOG</h3>
<div class="log" id="log"></div>

</div>

<script>
const token = "{token}";
let ws;
let chart;

// =========================
// WS CONNECT
// =========================
function connectWS() {{
    ws = new WebSocket(`ws://${{location.host}}/admin/ws`);

    ws.onmessage = (e) => {{
        const d = JSON.parse(e.data);

        if(d.type === "stats") {{
            document.getElementById("u").innerText = d.users;
            document.getElementById("t").innerText = d.trx;
            document.getElementById("b").innerText = d.balance;

            updateChart(d.balance);
        }}

        if(d.type === "log") {{
            document.getElementById("log").innerHTML =
                d.data.join("<br>");
        }}
    }};
}}

// =========================
// CHART
// =========================
function initChart() {{
    const ctx = document.getElementById("chart");

    chart = new Chart(ctx, {{
        type: "line",
        data: {{
            labels: [],
            datasets: [{{
                label: "Income",
                data: [],
                borderColor: "#22c55e"
            }}]
        }}
    }});
}}

function updateChart(v) {{
    const t = new Date().toLocaleTimeString();

    chart.data.labels.push(t);
    chart.data.datasets[0].data.push(v);

    if(chart.data.labels.length > 20) {{
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }}

    chart.update();
}}

// =========================
// USERS
// =========================
async function loadUsers() {{
    const res = await fetch(`/admin/api/users?token=${{token}}`);
    const data = await res.json();

    document.getElementById("users").innerHTML =
        data.map(u => `
            <div class="card" onclick="selectUser(${{u.user_id}})">
                👤 ${{u.username || "no_username"}}<br>
                ID: ${{u.user_id}}
            </div>
        `).join("");
}}

// =========================
// USER DETAIL
// =========================
async function selectUser(id) {{
    const res = await fetch(`/admin/api/user/detail?token=${{token}}&user_id=${{id}}`);
    const d = await res.json();

    document.getElementById("detail").innerHTML = `
        <h3>USER DETAIL</h3>
        ID: ${{d.user_id}}<br>
        Username: ${{d.username}}<br>
        Balance: Rp ${{d.balance}}<br>
        Bank: ${{d.bank || "-"}}
    `;
}}

// =========================
// BROADCAST
// =========================
async function broadcastMsg() {{
    await fetch(`/admin/api/broadcast?token=${{token}}`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ message: document.getElementById("msg").value }})
    }});
}}

// =========================
// MAINTENANCE
// =========================
async function maint(v) {{
    await fetch(`/admin/api/maintenance?token=${{token}}&v=${{v}}`, {{
        method: "POST"
    }});
}}

// =========================
// INIT
// =========================
window.onload = () => {{
    connectWS();
    initChart();
    loadUsers();
}};
</script>

</body>
</html>
"""


# =========================
# API: STATS (fallback)
# =========================
@router.get("/admin/api/realtime")
async def realtime(token: str = Query(default="")):

    if not check_token(token):
        return {"error": "unauthorized"}

    pool = get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        trx = await conn.fetchval("SELECT COUNT(*) FROM transactions") or 0
        balance = await conn.fetchval("SELECT COALESCE(SUM(balance),0) FROM users") or 0

    return {"users": users, "trx": trx, "balance": int(balance)}


# =========================
# USERS
# =========================
@router.get("/admin/api/users")
async def users(token: str = Query(default="")):

    if not check_token(token):
        return {"error": "unauthorized"}

    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT user_id, username
            FROM users
            ORDER BY user_id DESC
            LIMIT 100
        """)

    return [dict(r) for r in rows]


# =========================
# USER DETAIL
# =========================
@router.get("/admin/api/user/detail")
async def user_detail(token: str, user_id: int):

    if not check_token(token):
        return {"error": "unauthorized"}

    pool = get_pool()

    async with pool.acquire() as conn:
        user = await conn.fetchrow("""
            SELECT user_id, username, balance, bank
            FROM users
            WHERE user_id=$1
        """, user_id)

        codes = await conn.fetch("""
            SELECT code, price
            FROM codes
            WHERE user_id=$1
        """, user_id)

    return {
        **dict(user),
        "codes": [dict(c) for c in codes]
    }


# =========================
# BROADCAST
# =========================
@router.post("/admin/api/broadcast")
async def admin_broadcast(token: str, request: Request):

    if not check_token(token):
        return {"error": "unauthorized"}

    data = await request.json()
    await broadcast(data.get("message", ""))

    await push_live_log("📢 Broadcast sent")

    return {"ok": True}


# =========================
# MAINTENANCE TOGGLE
# =========================
@router.post("/admin/api/maintenance")
async def maintenance(token: str, v: bool):

    if not check_token(token):
        return {"error": "unauthorized"}

    set_maintenance(v)

    await send_group(
        "⚙️ MAINTENANCE ‼️ Sistem Bot Dalam Perbaikan" if v else "✅ MAINTENANCE Done ✅ Bot Selesai Dalam Perbaikan"
    )

    await push_live_log(f"Maintenance set to {v}")

    return {"ok": True}
