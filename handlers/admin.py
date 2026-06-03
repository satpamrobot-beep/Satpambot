import asyncio
import time

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from config import OWNER_ID
from database import db

router = Router()

START_TIME = time.time()


# =========================
# OWNER CHECK
# =========================

def is_owner(user_id):

    return user_id == OWNER_ID


# =========================
# ADMIN PANEL
# =========================

@router.message(
    Command("adminpanel")
)
async def admin_panel(
    message: Message
):

    if not is_owner(
        message.from_user.id
    ):
        return

    await message.reply(
"""
⚙ Owner Panel

/statistikadmin
/broadcastadmin
/ping
"""
    )


# =========================
# PING
# =========================

@router.message(
    Command("ping")
)
async def ping(
    message: Message
):

    if not is_owner(
        message.from_user.id
    ):
        return

    await message.reply(
        "🏓 Pong"
    )


# =========================
# STATS
# =========================

@router.message(
    Command("statistikadmin")
)
async def statistik_admin(
    message: Message
):

    if not is_owner(
        message.from_user.id
    ):
        return

    users = await db.count_users()

    groups = await db.count_groups()

    uptime = int(
        time.time() - START_TIME
    )

    hours = uptime // 3600
    minutes = (uptime % 3600) // 60

    await message.reply(
f"""
📊 BOT STATISTICS

👤 Users : {users}

👥 Groups : {groups}

⏳ Uptime : {hours}h {minutes}m
"""
    )


# =========================
# BROADCAST
# =========================

@router.message(
    Command("broadcastadmin")
)
async def broadcast_admin(
    message: Message
):

    if not is_owner(
        message.from_user.id
    ):
        return

    if not message.reply_to_message:

        return await message.reply(
            "Reply pesan untuk broadcast."
        )

    status = await message.reply(
        "📢 Broadcast dimulai..."
    )

    success = 0
    failed = 0

    targets = set()

    async with db.pool.acquire() as conn:

        users = await conn.fetch(
            """
            SELECT user_id
            FROM users
            """
        )

        groups = await conn.fetch(
            """
            SELECT chat_id
            FROM groups
            """
        )

    for row in users:

        targets.add(
            row["user_id"]
        )

    for row in groups:

        targets.add(
            row["chat_id"]
        )

    total = len(
        targets
    )

    for i, target in enumerate(
        targets,
        start=1
    ):

        try:

            await message.reply_to_message.copy_to(
                target
            )

            success += 1

        except TelegramBadRequest:

            failed += 1

        except Exception:

            failed += 1

        if i % 100 == 0:

            try:

                await status.edit_text(
f"""
📢 Broadcast berjalan...

Done : {i}/{total}

✅ Success : {success}

❌ Failed : {failed}
"""
                )

            except:

                pass

        await asyncio.sleep(
            0.08
        )

    try:

        async with db.pool.acquire() as conn:

            await conn.execute(
                """
                INSERT INTO broadcast_logs(
                    total_sent,
                    failed
                )

                VALUES($1,$2)
                """,
                success,
                failed
            )

    except:

        pass

    await status.edit_text(
f"""
✅ Broadcast selesai

Targets : {total}

Success : {success}

Failed : {failed}
"""
    )
