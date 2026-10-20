"""Admin route authorization, rate limits and edit feedback."""

from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes import admin
from app.core.config import get_settings
from app.main import app
from app.models.schemas import ProductCreate
from app.services.dependencies import get_product_service


async def login(client):
    prefix = get_settings().admin_route
    await client.get(f"{prefix}/login")
    token = client.cookies.get("csrf_token")
    response = await client.post(
        f"{prefix}/login",
        data={"csrf_token": token, "username": "admin", "password": "admin123"},
    )
    assert response.status_code == 303
    return token


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    ["add", "edit/missing", "delete/missing", "delete-image/missing/image.jpg", "primary-image/missing/image.jpg"],
)
async def test_all_product_actions_require_authentication(action):
    prefix = get_settings().admin_route
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            f"{prefix}/products/{action}", data={"csrf_token": "bad", "name": "Test"}
        )
    assert response.status_code == 303
    assert response.headers["location"] == f"{prefix}/login"


@pytest.mark.asyncio
async def test_image_removal_honors_product_write_limit(monkeypatch):
    prefix = get_settings().admin_route
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = await login(client)
        calls = []

        async def deny(*args):
            calls.append(args)
            return False

        monkeypatch.setattr(admin, "allow_request", deny)
        response = await client.post(
            f"{prefix}/products/delete-image/missing/image.jpg",
            data={"csrf_token": token},
        )
    assert response.status_code == 303
    assert calls and calls[0][1:] == (20, 60)
    assert calls[0][0].startswith("products:")
    assert (
        "Too many requests"
        in parse_qs(urlsplit(response.headers["location"]).query)["error"][0]
    )


@pytest.mark.asyncio
async def test_edit_feedback_category_and_logout():
    prefix = get_settings().admin_route
    service = get_product_service()
    product = await service.create_product(
        ProductCreate(name="Original", category="Tools"), []
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = await login(client)
        root = await client.get(prefix)
        assert root.headers["location"] == f"{prefix}/dashboard"
        page = await client.get(f"{prefix}/products", params={"msg": "A+B & C"})
        assert "A+B &amp; C" in page.text
        saved = await client.post(
            f"{prefix}/products/edit/{product.id}",
            data={
                "csrf_token": token,
                "name": "Renamed",
                "category": "Tools",
                "new_category": "   ",
            },
        )
        assert "msg=" in saved.headers["location"]
        assert service.get_product(product.id).category == "Tools"
        invalid = await client.post(
            f"{prefix}/products/edit/{product.id}",
            data={"csrf_token": token, "name": "X" * 256, "category": "Tools"},
        )
        assert (
            urlsplit(invalid.headers["location"]).path
            == f"{prefix}/products/edit/{product.id}"
        )
        assert "error=" in invalid.headers["location"]
        blocked = await client.post(
            f"{prefix}/products/delete/{product.id}", data={"csrf_token": "wrong"}
        )
        assert blocked.status_code == 403
        assert service.get_product(product.id).name == "Renamed"
        copied_session = client.cookies.get(get_settings().session_cookie_name)
        logged_out = await client.post(f"{prefix}/logout", data={"csrf_token": token})
        assert logged_out.headers["location"] == f"{prefix}/login"
        assert get_settings().session_cookie_name not in client.cookies
        client.cookies.set(get_settings().session_cookie_name, copied_session)
        protected = await client.get(f"{prefix}/dashboard")
        assert protected.status_code == 303


@pytest.mark.asyncio
async def test_make_primary_image_reorders_gallery():
    import io

    from PIL import Image

    class Upload:
        filename = "photo.jpg"

        def __init__(self, color):
            buf = io.BytesIO()
            Image.new("RGB", (40, 40), color).save(buf, "JPEG")
            self.content = buf.getvalue()

        async def read(self, size=-1):
            return self.content if size < 0 else self.content[:size]

    service = get_product_service()
    product = await service.create_product(
        ProductCreate(name="Gallery order", category="Tools"),
        [Upload("red"), Upload("blue"), Upload("green")],
    )
    first, second, third = service.get_product_images(product)
    prefix = get_settings().admin_route
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        token = await login(client)
        response = await client.post(
            f"{prefix}/products/primary-image/{product.id}/{third}",
            data={"csrf_token": token},
        )
        assert response.status_code == 303
        missing = await client.post(
            f"{prefix}/products/primary-image/{product.id}/nope.jpg",
            data={"csrf_token": token},
        )
        assert "error=" in missing.headers["location"]
        bad_csrf = await client.post(
            f"{prefix}/products/primary-image/{product.id}/{second}",
            data={"csrf_token": "bad"},
        )
        assert bad_csrf.status_code == 403
    updated = service.get_product(product.id)
    assert service.get_product_images(updated) == [third, first, second]
    assert updated.image == third
