from __future__ import annotations

import os
import time
from typing import Callable, Optional

try:
    # some editors/linters will flag this import if redis isn't installed in the dev environment
    # silence that with a type-ignore; runtime fallback handles missing package.
    import redis.asyncio as aioredis  # type: ignore[import]
except Exception:
    aioredis = None

# Redis-backed sliding-window limiter. Uses a Redis sorted set per key storing timestamps.
# Fallback: if REDIS_URL not set or redis lib missing, the allow_request will conservatively allow requests.

_redis_client: Optional[object] = None


def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    url = os.getenv("REDIS_URL", "")
    # In production require Redis and REDIS_URL to be set.
    from app.core.config import get_settings

    settings = get_settings()
    if settings.is_production:
        if aioredis is None:
            raise RuntimeError("Redis package is required in production. Install 'redis' and set REDIS_URL.")
        if not url:
            raise RuntimeError("REDIS_URL environment variable must be set in production.")
    if not url or aioredis is None:
        # In non-production environments we allow missing redis (tests/local dev), but in production
        # get_redis_client will have raised earlier. Return None to indicate unavailable client.
        return None
    _redis_client = aioredis.from_url(url)
    return _redis_client


async def allow_request(key: str, max_requests: int, window_seconds: int) -> bool:
    """Distributed rate limit check. Returns True if the request is allowed."""
    r = get_redis_client()
    now = int(time.time())
    window_start = now - window_seconds
    if r is None:
        # Fail-closed: if Redis is unavailable, deny requests to avoid bypassing rate limits.
        # In non-production, to ease development/tests, we allow requests.
        from app.core.config import get_settings

        settings = get_settings()
        if settings.is_production:
            return False
        return True

    key_name = f"rl:{key}"
    # Use a sorted set: add current timestamp, remove old entries, get cardinality, set expiry
    pipe = r.pipeline()
    pipe.zadd(key_name, {str(now): now})
    pipe.zremrangebyscore(key_name, 0, window_start)
    pipe.zcard(key_name)
    pipe.expire(key_name, window_seconds + 5)
    _, _, count, _ = await pipe.execute()
    return int(count) <= max_requests


def rate_limit_decorator(key_fn: Callable, max_requests: int, window_seconds: int):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            allowed = await allow_request(key, max_requests, window_seconds)
            if not allowed:
                from fastapi import HTTPException
                from starlette.status import HTTP_429_TOO_MANY_REQUESTS

                raise HTTPException(status_code=HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
            return await func(*args, **kwargs)

        return wrapper

    return decorator
