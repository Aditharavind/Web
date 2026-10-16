"""Production HTTP configuration checks; external service startup is separate."""

import os
import secrets
import subprocess
import sys

from app.core.config import BASE_DIR, pwd_context


def test_production_https_hosts_headers_and_cookies(tmp_path):
    env = dict(
        os.environ,
        ENVIRONMENT="production",
        SITE_URL="https://nawaglobalgtd.com",
        DATABASE_URL=f"sqlite:///{tmp_path}/production-check.db",
        UPLOAD_DIR=str(tmp_path / "uploads"),
        SECRET_KEY=secrets.token_urlsafe(48),
        ADMIN_USERNAME="test-owner",
        ADMIN_PASSWORD_HASH=pwd_context.hash("production-check-password"),
        SECURE_COOKIES="1",
        TRUSTED_HOSTS="nawaglobalgtd.com",
        SENTRY_DSN="",
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BASE_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    script = """
import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.database.db import ensure_database_schema

async def check():
    ensure_database_schema()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://nawaglobalgtd.com") as client:
        response = await client.get("/health")
        assert response.status_code == 307
        assert response.headers["location"] == "https://nawaglobalgtd.com/health"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://nawaglobalgtd.com") as client:
        response = await client.get("/admin12/login")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["strict-transport-security"].startswith("max-age=")
        assert "upgrade-insecure-requests" in response.headers["content-security-policy"]
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/health", headers={"host": "untrusted.invalid"})).status_code == 400
asyncio.run(check())
"""
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=BASE_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
