import asyncio
from typing import List, Dict, Any
from collections import deque
from datetime import datetime


# =========================================================
# MAINTENANCE STATE (THREAD SAFE + CONSISTENT)
# =========================================================
_maintenance: bool = False
_lock = asyncio.Lock()


async def set_maintenance(value: bool):
    """
    Toggle maintenance mode (async safe)
    """
    global _maintenance
    async with _lock:
        _maintenance = bool(value)


def is_maintenance() -> bool:
    """
    Check maintenance status
    """
    return _maintenance


# =========================================================
# LIVE LOG SYSTEM (HIGH PERFORMANCE BUFFER)
# =========================================================
LOG_BUFFER: deque = deque(maxlen=200)


def push_log(text: str, level: str = "info"):
    """
    Push log realtime ke admin dashboard + websocket
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    LOG_BUFFER.append({
        "time": timestamp,
        "level": level,
        "message": text
    })


def get_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Ambil log terbaru (untuk websocket / API)
    """
    return list(LOG_BUFFER)[-limit:]


def clear_logs():
    """
    Reset semua logs
    """
    LOG_BUFFER.clear()


# =========================================================
# EVENT TRACKING SYSTEM (REALTIME ANALYTICS)
# =========================================================
EVENTS: Dict[str, int] = {
    "payment": 0,
    "withdraw": 0,
    "broadcast": 0,
    "blocked_user": 0,
    "login": 0,
    "error": 0,
}


def inc_event(name: str, value: int = 1):
    """
    Increment event counter
    """
    if name in EVENTS:
        EVENTS[name] += value
    else:
        EVENTS[name] = value


def get_events() -> Dict[str, int]:
    return EVENTS


# =========================================================
# LIVE METRICS SNAPSHOT (FOR WEBSOCKET DASHBOARD)
# =========================================================
def get_state_snapshot(extra: dict | None = None) -> Dict[str, Any]:
    """
    Snapshot real-time untuk admin dashboard websocket
    """

    snapshot = {
        "maintenance": _maintenance,
        "events": EVENTS,
        "logs": list(LOG_BUFFER)[-20:],  # last 20 logs
        "timestamp": datetime.utcnow().isoformat()
    }

    if extra:
        snapshot.update(extra)

    return snapshot


# =========================================================
# SAFE WRAPPER (ANTI CRASH LOGGER)
# =========================================================
def safe_log(text: str, level: str = "info"):
    """
    Logging aman (tidak crash kalau error)
    """
    try:
        push_log(text, level)
    except Exception:
        pass


def safe_event(name: str):
    """
    Event tracker aman
    """
    try:
        inc_event(name)
    except Exception:
        pass
