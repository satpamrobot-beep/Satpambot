from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from bot.db.database import get_pool
import os

router = APIRouter()

# =========================
# CONFIG
# =========================
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")


def check_token(token: str) -> bool:
    return token == ADMIN_TOKEN


# =========================
# DASHBOARD PAGE
# =========================
@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(token: str = Query(default="")):

    if not check_token(token):
        return HTMLResponse("<h1>403 Forbidden</h1>", status_code=403)

    return """
<!DOCTYPE html>
<html>
<head>
<title>Admin Dashboard</title>

<script>
const token = new URLSearchParams(window.location.search).get("token");

async function loadStats(){
    const res = await fetch(`/admin/api/stats?token=${token}`);
    const d = await res.json();

    document.getElementById("users").innerText = d.users;
    document.getElementById("income").innerText = d.income;
    document.getElementById("trx").innerText = d.trx;
}

async function loadWithdraw(){
    const res = await fetch(`/admin/api/withdraws?token=${token}`);
    const data = await res.json();

    let html = "<h3>💸 Withdraw Requests</h3>";

    data.forEach(w => {
        html += `
        <div style="padding:10px;margin:10px;background:#222;border-radius:10px">
            <b>User:</b> ${w.user_id}<br>
            <b>Amount:</b> Rp ${w.amount}<br>
            <b>Status:</b> ${w.status}<br>

            <button onclick="actionWD(${w.id}, 'approve')">✅ Approve</button>
            <button onclick="actionWD(${w.id}, 'reject')">❌ Reject</button>
        </div>`;
    });

    document.getElementById("wd").innerHTML = html;
}

async function actionWD(id, action){
    await fetch(`/admin/api/withdraw/action?token=${token}&wd_id=${id}&action=${action}`, {
        method: "POST"
    });

    loadWithdraw();
}

setInterval(loadStats, 3000);
window.onload = () => {
    loadStats();
    loadWithdraw();
};
</script>

<style>
body{
    background:#0f0f0f;
    color:white;
    font-family:Arial;
    text-align:center;
}

.box{
    display:inline-block;
    padding:20px;
    margin:10px;
    background:#1f1f1f;
    width:200px;
    border-radius:10px;
}

button{
    margin:5px;
    padding:5px 10px;
    cursor:pointer;
}
</style>

</head>

<body>

<h1>🛠 EarnFile Admin Panel</h1>

<div class="box">
<h3>Users</h3>
<h2 id="users">0</h2>
</div>

<div class="box">
<h3>Income</h3>
<h2 id="income">0</h2>
</div>

<div class="box">
<h3>Transactions</h3>
<h2 id="trx">0</h2>
</div>

<div id="wd"></div>

</body>
</html>
"""


# =========================
# STATS API
# =========================
@router.get("/admin/api/stats")
async def stats(token: str = Query(default="")):

    if not check_token(token):
        return {"error": "unauthorized"}

    pool = get_pool()

    async with pool.acquire() as conn:
        users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
        income = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM transactions") or 0
        trx = await conn.fetchval("SELECT COUNT(*) FROM transactions") or 0

    return {
        "users": users,
        "income": int(income),
        "trx": trx
    }


# =========================
# WITHDRAW LIST
# =========================
@router.get("/admin/api/withdraws")
async def withdraws(token: str = Query(default="")):

    if not check_token(token):
        return {"error": "unauthorized"}

    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, user_id, amount, status
            FROM withdrawals
            ORDER BY id DESC
            LIMIT 50
        """)

    return [dict(r) for r in rows]


# =========================
# WITHDRAW ACTION (APPROVE / REJECT)
# =========================
@router.post("/admin/api/withdraw/action")
async def withdraw_action(
    token: str,
    wd_id: int,
    action: str
):

    if not check_token(token):
        return {"error": "unauthorized"}

    pool = get_pool()

    async with pool.acquire() as conn:

        if action == "approve":
            await conn.execute("""
                UPDATE withdrawals SET status='APPROVED'
                WHERE id=$1
            """, wd_id)

        elif action == "reject":
            await conn.execute("""
                UPDATE withdrawals SET status='REJECTED'
                WHERE id=$1
            """, wd_id)

    return {"ok": True}
