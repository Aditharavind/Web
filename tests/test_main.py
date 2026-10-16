"""Regression checks for application lifecycle and response middleware."""
from unittest.mock import AsyncMock, Mock

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "startup", "application", "close"])
async def test_lifespan_always_releases_resources(monkeypatch, failure):
    redis = Mock(ping=AsyncMock(), aclose=AsyncMock())
    if failure == "startup":
        redis.ping.side_effect = RuntimeError("startup failure")
    if failure == "close":
        redis.aclose.side_effect = RuntimeError("close failure")
    engine = Mock()
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "ensure_database_schema", Mock())
    monkeypatch.setattr(main, "get_redis_client", lambda: redis)

    async def run():
        async with main.lifespan(main.app):
            if failure == "application":
                raise RuntimeError("application failure")

    if failure:
        with pytest.raises(RuntimeError, match=f"{failure} failure"):
            await run()
    else:
        await run()
    redis.aclose.assert_awaited_once()
    engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test_csrf_cookies_only_on_html_pages():
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://testserver") as client:
        for path in ["/health", "/static/css/app.css", "/uploads/nonexistent.jpg"]:
            response = await client.get(path)
            assert "set-cookie" not in response.headers, path
        first = await client.get("/contact")
        assert client.cookies.get("csrf_token")
        assert "set-cookie" in first.headers
        second = await client.get("/contact")
        assert "set-cookie" not in second.headers
        admin = await client.get(f"{main.settings.admin_route}/login")
        assert admin.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
@pytest.mark.parametrize("accept", ["text/html", "application/json"])
async def test_http_error_preserves_allow_header(accept):
    async with AsyncClient(transport=ASGITransport(app=main.app), base_url="http://testserver") as client:
        response = await client.post("/health", headers={"accept": accept})
    assert response.status_code == 405
    assert "GET" in response.headers["allow"]
