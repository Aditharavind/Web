"""Atomic distributed limits, with a bounded development-only fallback."""
from __future__ import annotations

import os
import time
import secrets
from collections import OrderedDict, deque

import redis.asyncio as aioredis

from app.core.config import get_settings

_redis_client = None
_local: OrderedDict[str, deque[float]] = OrderedDict()
_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local maximum = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
if redis.call('ZCARD', key) >= maximum then return 0 end
redis.call('ZADD', key, now, ARGV[4])
redis.call('EXPIRE', key, math.ceil(window) + 1)
return 1
"""


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL", "")
    if not url:
        if get_settings().is_production:
            raise RuntimeError("REDIS_URL is required in production.")
        return None
    _redis_client = aioredis.from_url(url)
    return _redis_client


async def allow_request(key: str, max_requests: int, window_seconds: int) -> bool:
    redis = get_redis_client()
    if redis is not None:
        return bool(await redis.eval(
            _SCRIPT, 1, f"rl:{key}:{window_seconds}:{max_requests}",
            time.time(), window_seconds, max_requests, secrets.token_hex(16),
        ))
    now = time.monotonic()
    bucket_key = f"{key}:{window_seconds}:{max_requests}"
    bucket = _local.setdefault(bucket_key, deque())
    _local.move_to_end(bucket_key)
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    allowed = len(bucket) < max_requests
    if allowed:
        bucket.append(now)
    while len(_local) > 10000:
        _local.popitem(last=False)
    return allowed
