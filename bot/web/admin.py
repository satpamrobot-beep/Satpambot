from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from bot.db.database import get_pool
from services.notify import send_group, broadcast

import os

router = APIRouter()

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")

def check_token(token: str) -> bool:
    return token == ADMIN_TOKEN


# =========================
# ADMIN DASHBOARD
# =========================
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(token: str = Query(default="")):

    if not check_token(token):
        return HTMLResponse("403 Forbidden", status_code=403)

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Admin Control Center</title>

<script>
const token = "{token}";
let selectedUser = null;

async function loadUsers(){{
    const res = await fetch(`/admin/api/users?token=${{token}}`);
    const data = await res.json();

    let html = "<h3>👥 USER LIST</h3>";

    data.forEach(u => {{
        html += `
        <div style="padding:10px;margin:5px;background:#222;cursor:pointer"
             onclick="selectUser(${u.user_id})">
            👤 ${u.username || "no_username"} <br>
            ID: ${u.user_id}
        </div>`;
    }});

    document.getElementById("users").innerHTML = html;
}}

async function selectUser(id){{
    selectedUser = id;

    const res = await fetch(`/admin/api/user/detail?token=${{token}}&user_id=${{id}}`);
    const d = await res.json();

    document.getElementById("detail").innerHTML = `
        <h3>📌 USER DETAIL</h3>
        <b>ID:</b> ${d.user_id}<br>
        <b>Username:</b> ${d.username}<br>
        <b>Balance:</b> Rp ${d.balance}<br>
        <b>Bank:</b> ${d.bank || "-"}<br>
        <hr>
        <h4>📦 Codes</h4>
        ${d.codes.map(c => `<div>🔑 ${c.code} | Rp ${c.price}</div>`).join("")}
    `;
}}

async function broadcast(){{
    const msg = document.getElementById("bc").value;

    await fetch(`/admin/api/broadcast?token=${{token}}`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ message: msg }})
    }});

    alert("Broadcast sent");
}}

async function toggleMaintenance(){{
    await fetch(`/admin/api/maintenance/toggle?token=${{token}}`, {{
        method: "POST"
    }});

    alert("Maintenance toggled");
}}

window.onload = loadUsers;
</script>

<style>
body{{
    background:#0f0f0f;
    color:white;
    font-family:Arial;
    display:flex;
}}

.panel{{
    width:30%;
    padding:10px;
    border-right:1px solid #333;
}}

.detail{{
    width:70%;
    padding:10px;
}}

input,button{{
    padding:10px;
    margin:5px;
}}
</style>
</head>

<body>

<div class="panel" id="users"></div>

<div class="detail">

    <div id="detail">Select user</div>

    <hr>

    <h3>📢 Broadcast</h3>
    <textarea id="bc" placeholder="message"></textarea><br>
    <button onclick="broadcast()">Send Broadcast</button>

    <hr>

    <button onclick="toggleMaintenance()">⚙️ Toggle Maintenance</button>

</div>

</body>
</html>
"""


# =========================
# USER LIST
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
# USER DETAIL (SALDO + BANK + CODES)
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
        "user_id": user["user_id"],
        "username": user["username"],
        "balance": user["balance"],
        "bank": user["bank"],
        "codes": [dict(c) for c in codes]
    }


# =========================
# BROADCAST SYSTEM
# =========================
@router.post("/admin/api/broadcast")
async def broadcast_api(token: str, payload: dict):

    if not check_token(token):
        return {"error": "unauthorized"}

    message = payload.get("message", "")

    await broadcast(message)

    await send_group(f"📢 BROADCAST SENT:\n{message}")

    return {"ok": True}


# =========================
# MAINTENANCE MODE (GLOBAL SWITCH)
# =========================
MAINTENANCE = False


@router.post("/admin/api/maintenance/toggle")
async def maintenance(token: str):

    global MAINTENANCE

    if not check_token(token):
        return {"error": "unauthorized"}

    MAINTENANCE = not MAINTENANCE

    await send_group(f"⚙️ Maintenance: {MAINTENANCE}")

    return {"maintenance": MAINTENANCE}


# =========================
# CHECK MAINTENANCE (FOR BOT USE)
# =========================
def is_maintenance():
    return MAINTENANCE
