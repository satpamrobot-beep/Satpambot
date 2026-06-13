import asyncio
from typing import List, Dict, Any
from collections import deque
from datetime import datetime


# =========================================================
# GLOBAL STATE (SINGLE SOURCE OF TRUTH)
# =========================================================
class State:
    maintenance: bool = False
    lock = asyncio.Lock()


# =========================================================
# MAINTENANCE CONTROL (SAFE)
# =========================================================
async def set_maintenance(value: bool):
    async with State.lock:
        State.maintenance = bool(value)


def is_maintenance() -> bool:
    return State.maintenance


# =========================================================
# LIVE LOG SYSTEM
# =========================================================
LOG_BUFFER: deque = deque(maxlen=200)


def push_log(text: str, level: str = "info"):
    LOG_BUFFER.append({
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": text
    })


def get_logs(limit: int = 50) -> List[Dict[str, Any]]:
    return list(LOG_BUFFER)[-limit:]


def clear_logs():
    LOG_BUFFER.clear()


# =========================================================
# EVENT TRACKING
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
    EVENTS[name] = EVENTS.get(name, 0) + value


def get_events() -> Dict[str, int]:
    return EVENTS


# =========================================================
# SNAPSHOT (FOR WS / DASHBOARD)
# =========================================================
def get_state_snapshot(extra: dict | None = None) -> Dict[str, Any]:
    snapshot = {
        "maintenance": State.maintenance,
        "events": EVENTS,
        "logs": list(LOG_BUFFER)[-20:],
        "timestamp": datetime.utcnow().isoformat()
    }

    if extra:
        snapshot.update(extra)

    return snapshot


# =========================================================
# SAFE WRAPPER
# =========================================================
def safe_log(text: str, level: str = "info"):
    try:
        push_log(text, level)
    except:
        pass


def safe_event(name: str):
    try:
        inc_event(name)
    except:
        pass
