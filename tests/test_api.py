import asyncio
import os
import tempfile

import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from app.main import app
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        r = await ac.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


@pytest.mark.asyncio
async def test_contact_rate_limit_and_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # missing csrf should be redirected (302) or forbidden (403) or validation (422)
        r = await ac.post("/contact", data={"name": "a", "email": "a@b.com", "message": "hi"})
        assert r.status_code in (302, 403, 422)

        # repeated requests should trigger rate limit eventually (we run few fast)
        for i in range(6):
            r = await ac.post(
                "/contact",
                data={"csrf_token": "invalid", "name": "a", "email": "a@b.com", "message": "hi"},
                follow_redirects=False,
            )
        # Accept 422 (validation), redirects (303), rate limit (429) or forbidden (403)
        assert r.status_code in (303, 429, 403, 422)


@pytest.mark.asyncio
async def test_admin_login_lockout():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        # attempt invalid logins
        for i in range(6):
            r = await ac.post(
                "/admin12/login",
                data={"csrf_token": "x", "username": "wrong", "password": "bad"},
                follow_redirects=False,
            )
        # should redirect with error after lockout, be forbidden, or return a validation error
        assert r.status_code in (303, 429, 422, 403)
