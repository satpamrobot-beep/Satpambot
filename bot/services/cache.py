import time

USER_CACHE = {}
JOIN_CACHE = {}

JOIN_TTL = 60  # 1 menit cache join
USER_TTL = 120 # 2 menit cache user


def set_join(user_id: int, value: bool):
    JOIN_CACHE[user_id] = (value, time.time())


def get_join(user_id: int):
    data = JOIN_CACHE.get(user_id)

    if not data:
        return None

    value, ts = data

    if time.time() - ts > JOIN_TTL:
        return None

    return value


def set_user(user_id: int, data: dict):
    USER_CACHE[user_id] = (data, time.time())


def get_user(user_id: int):
    data = USER_CACHE.get(user_id)

    if not data:
        return None

    value, ts = data

    if time.time() - ts > USER_TTL:
        return None

    return value
