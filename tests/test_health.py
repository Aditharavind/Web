from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.api.routes import health


@pytest.mark.asyncio
async def test_health_is_not_cached():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_health_database_failure_returns_generic_503(monkeypatch):
    engine = Mock()
    engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("private connection details"))
    monkeypatch.setattr(health, "engine", engine)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "db": False}
    assert response.headers["cache-control"] == "no-store"
    assert "private" not in response.text
