import time
from typing import Dict, Tuple

# =========================
# CACHE STORAGE
# =========================
# key = (user_id, chat_id)
# value = (status: bool, expires_at: float)
JOIN_CACHE: Dict[Tuple[int, int], Tuple[bool, float]] = {}

# cache 60 detik (biar gak spam API)
CACHE_TTL = 60


def get_cache(user_id: int, chat_id: int):
    key = (user_id, chat_id)

    data = JOIN_CACHE.get(key)
    if not data:
        return None

    status, exp = data

    if time.time() > exp:
        JOIN_CACHE.pop(key, None)
        return None

    return status


def set_cache(user_id: int, chat_id: int, status: bool):
    key = (user_id, chat_id)
    JOIN_CACHE[key] = (status, time.time() + CACHE_TTL)


def clear_user_cache(user_id: int):
    keys = [k for k in JOIN_CACHE.keys() if k[0] == user_id]
    for k in keys:
        JOIN_CACHE.pop(k, None)


def clear_all_cache():
    JOIN_CACHE.clear()
