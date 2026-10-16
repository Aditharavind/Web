"""Rate-limit boundaries, Redis failure behavior, and lifecycle regression tests."""

from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest
from redis.exceptions import TimeoutError

from app.core import rate_limiter as limiter
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_client(monkeypatch):
    monkeypatch.setattr(limiter, "_redis_client", None)


def test_redis_connection_is_bounded_and_reused(monkeypatch):
    monkeypatch.setenv("REDIS_URL", " redis://localhost/0 ")
    factory = Mock(return_value=Mock())
    monkeypatch.setattr(limiter.aioredis, "from_url", factory)
    assert limiter.get_redis_client() is limiter.get_redis_client()
    factory.assert_called_once_with(
        "redis://localhost/0",
        socket_connect_timeout=2,
        socket_timeout=2,
        max_connections=20,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_closed_client_is_never_reused(monkeypatch, fails):
    old = Mock(aclose=AsyncMock(side_effect=RuntimeError("close") if fails else None))
    monkeypatch.setattr(limiter, "_redis_client", old)
    if fails:
        with pytest.raises(RuntimeError):
            await limiter.close_redis_client(old)
    else:
        await limiter.close_redis_client(old)
    monkeypatch.setenv("REDIS_URL", "redis://localhost/0")
    new = Mock()
    monkeypatch.setattr(limiter.aioredis, "from_url", Mock(return_value=new))
    assert limiter.get_redis_client() is new
    old.aclose.assert_awaited_once()


def test_production_requires_redis(monkeypatch):
    settings = replace(get_settings(), is_production=True)
    monkeypatch.setattr(limiter, "get_settings", lambda: settings)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        limiter.get_redis_client()


@pytest.mark.asyncio
async def test_local_limit_expiry_and_key_isolation(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(limiter.time, "monotonic", lambda: now[0])
    assert await limiter.allow_request("one", 2, 10)
    assert await limiter.allow_request("one", 2, 10)
    assert not await limiter.allow_request("one", 2, 10)
    assert await limiter.allow_request("two", 2, 10)
    now[0] = 110.0
    assert await limiter.allow_request("one", 2, 10)
    for index in range(10001):
        await limiter.allow_request(f"key-{index}", 1, 10)
    assert len(limiter._local) == 10000


@pytest.mark.asyncio
async def test_redis_errors_do_not_enable_local_fallback(monkeypatch):
    client = Mock(eval=AsyncMock(side_effect=TimeoutError("unavailable")))
    monkeypatch.setattr(limiter, "_redis_client", client)
    with pytest.raises(TimeoutError):
        await limiter.allow_request("admin", 2, 10)
    assert not limiter._local


@pytest.mark.asyncio
@pytest.mark.parametrize("maximum,window", [(0, 10), (2, 0), (-1, 10)])
async def test_invalid_limit_arguments(maximum, window):
    with pytest.raises(ValueError):
        await limiter.allow_request("admin", maximum, window)
