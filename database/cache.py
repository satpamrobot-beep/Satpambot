import time

cache = {}

def set_cache(key, value, ttl=60):
    cache[key] = (value, time.time() + ttl)

def get_cache(key):
    data = cache.get(key)
    if not data:
        return None
    value, exp = data
    if time.time() > exp:
        del cache[key]
        return None
    return value
