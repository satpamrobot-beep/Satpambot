import asyncio

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramRetryAfter
)

from config import OWNER_ID
from database import db

router = Router()


@router.message(
    Command("broadcastadmin")
)
async def broadcast_admin(
    message: Message
):

    # =========================
    # OWNER CHECK
    # =========================

    if message.from_user.id != OWNER_ID:

        return await message.reply(
            "Owner only."
        )

    # =========================
    # MUST REPLY MESSAGE
    # =========================

    if not message.reply_to_message:

        return await message.reply(
            "Reply pesan untuk broadcast."
        )

    # =========================
    # DB CHECK
    # =========================

    if not db.pool:

        return await message.reply(
            "Database belum connect."
        )

    status = await message.reply(
        "Broadcast dimulai..."
    )

    success = 0
    failed = 0

    targets = set()

    # =========================
    # LOAD TARGETS
    # =========================

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

    # =========================
    # BROADCAST LOOP
    # =========================

    for i, target in enumerate(targets):

        try:

            await message.reply_to_message.copy_to(
                target
            )

            success += 1

        except TelegramRetryAfter as e:

            await asyncio.sleep(
                e.retry_after
            )

            failed += 1

        except TelegramBadRequest:

            failed += 1

        except Exception:

            failed += 1

        if (i + 1) % 100 == 0:

            try:

                await status.edit_text(
                    f"""
📢 Broadcast berjalan...

Done : {i + 1}/{total}

✅ Success : {success}

❌ Failed : {failed}
"""
                )

            except:

                pass

        await asyncio.sleep(
            0.1
        )

    # =========================
    # SAVE LOG
    # =========================

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

    # =========================
    # DONE
    # =========================

    await status.edit_text(
        f"""
✅ Broadcast selesai

🎯 Targets : {total}

✅ Success : {success}

❌ Failed : {failed}
"""
    )
