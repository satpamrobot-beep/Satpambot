import time

user_last_message = {}

SPAM_LIMIT = 2  # detik

async def is_spam(user_id: int):
    now = time.time()

    if user_id in user_last_message:
        last = user_last_message[user_id]

        if now - last < SPAM_LIMIT:
            return True

    user_last_message[user_id] = now
    return False
