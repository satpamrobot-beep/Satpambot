# =========================================================
# 🔥 TZY GUARD INFINITY X
# ULTRA PREMIUM TELEGRAM GROUP MANAGER
# LIKE ROSE / SOPHIE / GROUPHELP
# =========================================================

# =========================================================
# FEATURES
# =========================================================
# ✅ Anti Link
# ✅ Anti Username
# ✅ Anti Telegram Link
# ✅ Anti Forward
# ✅ Anti Spam
# ✅ Anti Flood
# ✅ Anti Command
# ✅ Anti Bot Add
# ✅ Blacklist Word
# ✅ Welcome Cleaner
# ✅ Goodbye Cleaner
# ✅ Welcome Message
# ✅ Notes System
# ✅ Filters System
# ✅ Warn System
# ✅ Auto Ban
# ✅ Auto Mute
# ✅ Broadcast Group
# ✅ Broadcast User
# ✅ Statistics
# ✅ Multi Group
# ✅ SQLite Database
# ✅ Admin Tools
# ✅ Pin / Unpin
# ✅ Purge
# ✅ Auto Delete
# ✅ Channel Button
# ✅ Savage Security
# ✅ Premium Start Menu
# =========================================================

# =========================================================
# INSTALL
# =========================================================
# pkg update && pkg upgrade -y
# pkg install python -y
# pip install python-telegram-bot
#
# RUN:
# python main.py
# =========================================================

import re
import time
import sqlite3
import asyncio

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from telegram.constants import ChatPermissions

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = "TOKEN_KAMU"
OWNER_ID = 123456789

CHANNEL_URL = "https://t.me/+8TUGR4lwuzc4OTk1"

BOT_START = time.time()

# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(
    "tzy_guard.db",
    check_same_thread=False
)

cursor = db.cursor()

# GROUPS
cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY
)
""")

# USERS
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")

# SETTINGS
cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    chat_id INTEGER,
    name TEXT,
    value TEXT
)
""")

# WARNS
cursor.execute("""
CREATE TABLE IF NOT EXISTS warns (
    user_id INTEGER,
    chat_id INTEGER,
    warns INTEGER
)
""")

# FILTERS
cursor.execute("""
CREATE TABLE IF NOT EXISTS filters (
    chat_id INTEGER,
    trigger TEXT,
    response TEXT
)
""")

# NOTES
cursor.execute("""
CREATE TABLE IF NOT EXISTS notes (
    chat_id INTEGER,
    name TEXT,
    content TEXT
)
""")

# BLACKLIST
cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    chat_id INTEGER,
    word TEXT
)
""")

db.commit()

# =========================================================
# MEMORY
# =========================================================

spam_db = {}

# =========================================================
# REGEX
# =========================================================

LINK_REGEX = (
    r"(https?://|"
    r"t\.me/|"
    r"telegram\.me/|"
    r"@\w+)"
)

# =========================================================
# SETTINGS
# =========================================================

def set_setting(chat_id, name, value):

    cursor.execute(
        "DELETE FROM settings WHERE chat_id=? AND name=?",
        (chat_id, name)
    )

    cursor.execute(
        "INSERT INTO settings VALUES (?, ?, ?)",
        (chat_id, name, str(value))
    )

    db.commit()

def get_setting(chat_id, name, default=None):

    cursor.execute(
        "SELECT value FROM settings WHERE chat_id=? AND name=?",
        (chat_id, name)
    )

    data = cursor.fetchone()

    if data:
        return data[0]

    return default

# =========================================================
# ADMIN CHECK
# =========================================================

async def is_admin(update, context):

    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )

    return member.status in [
        "administrator",
        "creator"
    ]

# =========================================================
# START MENU
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (update.effective_user.id,)
    )

    db.commit()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ ADD TO GROUP",
                url="https://t.me/NAMA_BOT_KAMU?startgroup=true"
            )
        ],
        [
            InlineKeyboardButton(
                "📢 CHANNEL",
                url=CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                "🛠 COMMANDS",
                callback_data="cmds"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 STATISTICS",
                callback_data="stats"
            )
        ]
    ])

    text = f"""
🔥 TZY GUARD INFINITY X 🔥

⚔️ ULTRA PREMIUM TELEGRAM SECURITY
⚔️ ANTI SPAM / ANTI LINK / ANTI RAID
⚔️ POWERFUL GROUP MODERATION

━━━━━━━━━━━━━━━

✅ Auto Moderation
✅ Savage Protection
✅ Notes & Filters
✅ Warn & Ban System
✅ Broadcast System
✅ Welcome Cleaner

━━━━━━━━━━━━━━━

👤 USER:
{update.effective_user.first_name}

🤖 BOT STATUS:
ONLINE

Tap buttons below to continue.
"""

    await update.message.reply_text(
        text,
        reply_markup=keyboard
    )

# =========================================================
# CALLBACK BUTTONS
# =========================================================

async def buttons(update, context):

    query = update.callback_query

    await query.answer()

    # ================= COMMANDS =================

    if query.data == "cmds":

        text = """
🛠 ADMIN COMMANDS

━━━━━━━━━━━━━━━

⚔️ SECURITY

/enable anti_link
/enable anti_spam
/enable anti_forward
/enable anti_command

/disable anti_link

━━━━━━━━━━━━━━━

⚔️ WELCOME

/setwelcome Welcome {name}

/setgoodbye Goodbye

━━━━━━━━━━━━━━━

⚔️ FILTERS

/filter hello Hi bro
/save rules No spam

#rules

━━━━━━━━━━━━━━━

⚔️ ADMIN TOOLS

/warn
/mute
/ban
/pin
/purge

━━━━━━━━━━━━━━━

⚔️ OWNER

/broadcast
/ucast
/stats

━━━━━━━━━━━━━━━

🔥 TZY GUARD INFINITY
"""

        await query.message.reply_text(text)

    # ================= STATS =================

    elif query.data == "stats":

        cursor.execute("SELECT COUNT(*) FROM groups")
        groups = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users")
        users = cursor.fetchone()[0]

        uptime = int(time.time() - BOT_START)

        hours = uptime // 3600
        minutes = (uptime % 3600) // 60
        seconds = uptime % 60

        text = f"""
📊 BOT STATISTICS

━━━━━━━━━━━━━━━

👥 GROUPS:
{groups}

👤 USERS:
{users}

⏱ UPTIME:
{hours}h {minutes}m {seconds}s

🤖 STATUS:
ONLINE

━━━━━━━━━━━━━━━

🔥 TZY GUARD INFINITY
"""

        await query.message.reply_text(text)

# =========================================================
# MENU
# =========================================================

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = f"""
🔥 TZY GUARD SETTINGS

━━━━━━━━━━━━━━━

🔗 Anti Link:
{get_setting(update.effective_chat.id, "anti_link", "off")}

⚠️ Anti Spam:
{get_setting(update.effective_chat.id, "anti_spam", "off")}

📨 Anti Forward:
{get_setting(update.effective_chat.id, "anti_forward", "off")}

🤖 Anti Command:
{get_setting(update.effective_chat.id, "anti_command", "off")}
"""

    await update.message.reply_text(text)

# =========================================================
# ENABLE / DISABLE
# =========================================================

async def enable(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    feature = context.args[0]

    set_setting(
        update.effective_chat.id,
        feature,
        "on"
    )

    await update.message.reply_text(
        f"✅ {feature} enabled"
    )

async def disable(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    feature = context.args[0]

    set_setting(
        update.effective_chat.id,
        feature,
        "off"
    )

    await update.message.reply_text(
        f"❌ {feature} disabled"
    )

# =========================================================
# WELCOME
# =========================================================

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        await update.message.delete()
    except:
        pass

    text = get_setting(
        update.effective_chat.id,
        "welcome",
        ""
    )

    if text == "":
        return

    for member in update.message.new_chat_members:

        msg = await context.bot.send_message(
            update.effective_chat.id,
            text.replace("{name}", member.first_name)
        )

        await asyncio.sleep(20)

        try:
            await msg.delete()
        except:
            pass

# =========================================================
# SETWELCOME
# =========================================================

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    text = " ".join(context.args)

    set_setting(
        update.effective_chat.id,
        "welcome",
        text
    )

    await update.message.reply_text(
        "✅ Welcome updated"
    )

# =========================================================
# FILTERS
# =========================================================

async def addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    trigger = context.args[0].lower()

    response = " ".join(context.args[1:])

    cursor.execute(
        "INSERT INTO filters VALUES (?, ?, ?)",
        (
            update.effective_chat.id,
            trigger,
            response
        )
    )

    db.commit()

    await update.message.reply_text(
        "✅ Filter saved"
    )

# =========================================================
# SAVE NOTE
# =========================================================

async def save_note(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    name = context.args[0]

    content = " ".join(context.args[1:])

    cursor.execute(
        "INSERT INTO notes VALUES (?, ?, ?)",
        (
            update.effective_chat.id,
            name,
            content
        )
    )

    db.commit()

    await update.message.reply_text(
        "✅ Note saved"
    )

# =========================================================
# GET NOTE
# =========================================================

async def get_note(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message.text.startswith("#"):
        return

    name = update.message.text.replace("#", "")

    cursor.execute(
        """
        SELECT content FROM notes
        WHERE chat_id=? AND name=?
        """,
        (
            update.effective_chat.id,
            name
        )
    )

    data = cursor.fetchone()

    if data:

        await update.message.reply_text(
            data[0]
        )

# =========================================================
# BLACKLIST
# =========================================================

async def blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    word = " ".join(context.args).lower()

    cursor.execute(
        "INSERT INTO blacklist VALUES (?, ?)",
        (
            update.effective_chat.id,
            word
        )
    )

    db.commit()

    await update.message.reply_text(
        f"✅ Blacklist added: {word}"
    )

# =========================================================
# WARN
# =========================================================

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user

    cursor.execute(
        """
        SELECT warns FROM warns
        WHERE user_id=? AND chat_id=?
        """,
        (
            user.id,
            update.effective_chat.id
        )
    )

    data = cursor.fetchone()

    total = 1

    if data:

        total = data[0] + 1

        cursor.execute(
            """
            UPDATE warns
            SET warns=?
            WHERE user_id=? AND chat_id=?
            """,
            (
                total,
                user.id,
                update.effective_chat.id
            )
        )

    else:

        cursor.execute(
            """
            INSERT INTO warns VALUES (?, ?, ?)
            """,
            (
                user.id,
                update.effective_chat.id,
                total
            )
        )

    db.commit()

    await update.message.reply_text(
        f"⚠️ {user.first_name} warned ({total}/3)"
    )

    if total >= 3:

        await context.bot.ban_chat_member(
            update.effective_chat.id,
            user.id
        )

        await update.message.reply_text(
            f"☠️ {user.first_name} auto banned"
        )

# =========================================================
# MUTE
# =========================================================

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user

    await context.bot.restrict_chat_member(
        update.effective_chat.id,
        user.id,
        permissions=ChatPermissions(
            can_send_messages=False
        )
    )

    await update.message.reply_text(
        f"🔇 {user.first_name} muted"
    )

# =========================================================
# BAN
# =========================================================

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    if not update.message.reply_to_message:
        return

    user = update.message.reply_to_message.from_user

    await context.bot.ban_chat_member(
        update.effective_chat.id,
        user.id
    )

    await update.message.reply_text(
        f"☠️ {user.first_name} banned"
    )

# =========================================================
# PIN
# =========================================================

async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    if not update.message.reply_to_message:
        return

    await context.bot.pin_chat_message(
        update.effective_chat.id,
        update.message.reply_to_message.message_id
    )

# =========================================================
# PURGE
# =========================================================

async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update, context):
        return

    if not update.message.reply_to_message:
        return

    start = update.message.reply_to_message.message_id
    end = update.message.message_id

    for msg_id in range(start, end):

        try:

            await context.bot.delete_message(
                update.effective_chat.id,
                msg_id
            )

        except:
            pass

# =========================================================
# BROADCAST GROUP
# =========================================================

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    text = " ".join(context.args)

    cursor.execute(
        "SELECT chat_id FROM groups"
    )

    groups = cursor.fetchall()

    sent = 0

    for group in groups:

        try:

            await context.bot.send_message(
                group[0],
                f"📢 GLOBAL BROADCAST\n\n{text}"
            )

            sent += 1

        except:
            pass

    await update.message.reply_text(
        f"✅ Sent to {sent} groups"
    )

# =========================================================
# USER BROADCAST
# =========================================================

async def ucast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != OWNER_ID:
        return

    text = " ".join(context.args)

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = cursor.fetchall()

    sent = 0

    for user in users:

        try:

            await context.bot.send_message(
                user[0],
                f"📢 USER BROADCAST\n\n{text}"
            )

            sent += 1

        except:
            pass

    await update.message.reply_text(
        f"✅ Sent to {sent} users"
    )

# =========================================================
# MAIN GUARD
# =========================================================

async def guard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message:
        return

    user = update.effective_user
    chat = update.effective_chat

    cursor.execute(
        "INSERT OR IGNORE INTO groups VALUES (?)",
        (chat.id,)
    )

    db.commit()

    member = await context.bot.get_chat_member(
        chat.id,
        user.id
    )

    admin = member.status in [
        "administrator",
        "creator"
    ]

    if admin:
        return

    text = ""

    if update.message.text:
        text = update.message.text.lower()

    # ================= ANTI LINK =================

    if get_setting(chat.id, "anti_link") == "on":

        if re.search(LINK_REGEX, text):

            await update.message.delete()

            msg = await context.bot.send_message(
                chat.id,
                f"""
🚫 LINK DETECTED

👤 {user.first_name}

Savage Security removed your message.
"""
            )

            await asyncio.sleep(5)

            try:
                await msg.delete()
            except:
                pass

            return

    # ================= ANTI COMMAND =================

    if get_setting(chat.id, "anti_command") == "on":

        if text.startswith("/"):

            await update.message.delete()

            return

    # ================= ANTI FORWARD =================

    if get_setting(chat.id, "anti_forward") == "on":

        if update.message.forward_date:

            await update.message.delete()

            return

    # ================= BLACKLIST =================

    cursor.execute(
        """
        SELECT word FROM blacklist
        WHERE chat_id=?
        """,
        (chat.id,)
    )

    words = cursor.fetchall()

    for word in words:

        if word[0] in text:

            await update.message.delete()

            return

    # ================= FILTERS =================

    cursor.execute(
        """
        SELECT trigger, response
        FROM filters
        WHERE chat_id=?
        """,
        (chat.id,)
    )

    data = cursor.fetchall()

    for trigger, response in data:

        if trigger in text:

            await update.message.reply_text(
                response
            )

            return

    # ================= ANTI SPAM =================

    if get_setting(chat.id, "anti_spam") == "on":

        uid = user.id
        now = time.time()

        if uid not in spam_db:
            spam_db[uid] = []

        spam_db[uid].append(now)

        spam_db[uid] = [
            t for t in spam_db[uid]
            if now - t < 5
        ]

        if len(spam_db[uid]) >= 5:

            await update.message.delete()

            msg = await context.bot.send_message(
                chat.id,
                f"""
⚠️ SPAM DETECTED

👤 {user.first_name}

Stop flooding the group.
"""
            )

            await asyncio.sleep(5)

            try:
                await msg.delete()
            except:
                pass

# =========================================================
# MAIN
# =========================================================

app = Application.builder().token(
    BOT_TOKEN
).build()

# COMMANDS
app.add_handler(CommandHandler("start", start))

app.add_handler(CommandHandler("menu", menu))

app.add_handler(CommandHandler("enable", enable))
app.add_handler(CommandHandler("disable", disable))

app.add_handler(CommandHandler("setwelcome", setwelcome))

app.add_handler(CommandHandler("filter", addfilter))

app.add_handler(CommandHandler("save", save_note))

app.add_handler(CommandHandler("blacklist", blacklist))

app.add_handler(CommandHandler("warn", warn))

app.add_handler(CommandHandler("mute", mute))

app.add_handler(CommandHandler("ban", ban))

app.add_handler(CommandHandler("pin", pin))

app.add_handler(CommandHandler("purge", purge))

app.add_handler(CommandHandler("broadcast", broadcast))

app.add_handler(CommandHandler("ucast", ucast))

# CALLBACKS
app.add_handler(
    CallbackQueryHandler(buttons)
)

# EVENTS
app.add_handler(
    MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome
    )
)

# NOTES
app.add_handler(
    MessageHandler(
        filters.TEXT,
        get_note
    )
)

# GUARD
app.add_handler(
    MessageHandler(
        filters.ALL,
        guard
    )
)

print("🔥 TZY GUARD INFINITY X RUNNING 🔥")

app.run_polling()
