import re

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import get_settings
from app.core.rate_limiter import allow_request
from app.services.auth import SessionService
from app.core.exceptions import AuthenticationError


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}


@pytest.mark.asyncio
async def test_csrf_and_admin_authorization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(f"{get_settings().admin_route}/login", data={"csrf_token": "bad", "username": "admin", "password": "bad"})
        assert response.status_code == 403
        response = await client.get(f"{get_settings().admin_route}/products")
        assert response.status_code == 303
        assert response.headers["location"].endswith("/login")


@pytest.mark.asyncio
async def test_burst_rate_limit():
    results = [await allow_request("burst", 5, 60) for _ in range(8)]
    assert results == [True] * 5 + [False] * 3
    assert await allow_request("other-action", 5, 60)


@pytest.mark.asyncio
async def test_contact_uses_direct_channels_only():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        page = await client.get("/contact")
        assert 'href="https://wa.me/971505464847?text=' in page.text
        assert 'href="mailto:info@nawaglobalgtd.com?subject=' in page.text
        assert '<form' not in page.text
        response = await client.post("/contact", data={"message": "Hello"})
        assert response.status_code == 405


def test_production_rejects_missing_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="Missing production settings"):
            get_settings()
    finally:
        get_settings.cache_clear()


def test_plaintext_password_cannot_override_hash(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "bypass")
    with pytest.raises(AuthenticationError):
        SessionService(__import__("app.main", fromlist=["settings"]).settings).authenticate("admin", "bypass")


@pytest.mark.asyncio
async def test_pages_and_local_assets_resolve():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        for path in ["/", "/about", "/contact", "/catalog", "/robots.txt", "/sitemap.xml"]:
            response = await client.get(path)
            assert response.status_code == 200, path
            for url in re.findall(r'(?:src|href)="([^\"]+/static/[^\"]+)"', response.text):
                asset = await client.get(url)
                assert asset.status_code == 200, url


@pytest.mark.asyncio
async def test_old_services_page_redirects_to_home_supply_section():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/services")
    assert response.status_code == 301
    assert response.headers["location"] == "/#supply"


@pytest.mark.asyncio
async def test_robots_does_not_advertise_admin_path():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        robots = (await client.get("/robots.txt")).text
    assert "admin" not in robots.lower()
    assert "Sitemap:" in robots


@pytest.mark.asyncio
async def test_visitor_aggregates():
    from app.services.visit_service import VisitService
    service = VisitService()
    service.log_visit("127.0.0.1")
    service.log_visit("127.0.0.1")
    assert service.summary() == {"total": 2, "today": 2, "unique_ips": 1}
    for period in ["today", "week", "month", "year", "all"]:
        result = service.analytics(period)
        assert result["total"] == 2
        assert sum(item["count"] for item in result["chart"]) == 2
