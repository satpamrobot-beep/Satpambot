import time
import asyncio
from typing import Dict, Tuple, Optional

# =========================
# CACHE STORAGE
# =========================
# key = (user_id, chat_id)
# value = (status: bool, expires_at: float)
JOIN_CACHE: Dict[Tuple[int, int], Tuple[bool, float]] = {}

CACHE_TTL = 60  # detik

# biar aman kalau async banyak request
_lock = asyncio.Lock()


# =========================
# GET CACHE
# =========================
def get_cache(user_id: int, chat_id: int) -> Optional[bool]:
    key = (user_id, chat_id)

    data = JOIN_CACHE.get(key)
    if not data:
        return None

    status, exp = data

    # expired → hapus
    if time.time() > exp:
        JOIN_CACHE.pop(key, None)
        return None

    return status


# =========================
# SET CACHE
# =========================
async def set_cache(user_id: int, chat_id: int, status: bool):
    key = (user_id, chat_id)

    async with _lock:
        JOIN_CACHE[key] = (
            status,
            time.time() + CACHE_TTL
        )


# =========================
# CLEAR USER CACHE
# =========================
async def clear_user_cache(user_id: int):
    async with _lock:
        keys = [k for k in list(JOIN_CACHE.keys()) if k[0] == user_id]

        for k in keys:
            JOIN_CACHE.pop(k, None)


# =========================
# CLEAR ALL CACHE
# =========================
async def clear_all_cache():
    async with _lock:
        JOIN_CACHE.clear()
