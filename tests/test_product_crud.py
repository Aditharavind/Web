import io

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.core.exceptions import ValidationError
from app.main import app
from app.models.schemas import ProductCreate, ProductUpdate
from app.services.dependencies import get_product_service


class Upload:
    def __init__(self, content, filename="test.jpg"):
        self.filename = filename
        self.content = content

    async def read(self, size=-1):
        return self.content if size < 0 else self.content[:size]


def image_upload(color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buf, "JPEG")
    return Upload(buf.getvalue())


@pytest.mark.asyncio
async def test_product_images_append_without_overwriting():
    service = get_product_service()
    product = await service.create_product(ProductCreate(name="Test", category="Tools"), [image_upload()])
    original = product.images[0]
    before = (service.image_service.upload_dir / original).read_bytes()
    updated = await service.update_product(product.id, ProductUpdate(name="Updated", category="Tools"), [image_upload("blue")])
    assert len(updated.images) == 2
    assert len(set(updated.images)) == 2
    assert (service.image_service.upload_dir / original).read_bytes() == before
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/product/{product.id}")
    assert response.status_code == 200
    assert "Updated" in response.text
    service.delete_product(product.id)
    assert all(not (service.image_service.upload_dir / name).exists() for name in updated.images)


@pytest.mark.asyncio
async def test_partial_upload_failure_removes_saved_files():
    service = get_product_service()
    before = set(service.image_service.upload_dir.iterdir())
    with pytest.raises(ValidationError):
        await service.create_product(ProductCreate(name="Bad upload", category="Tools"), [image_upload(), Upload(b"invalid")])
    assert set(service.image_service.upload_dir.iterdir()) == before
    assert service.list_products() == []


@pytest.mark.asyncio
async def test_template_rendering_home():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "NAWA Global" in response.text
    assert "data-theme-toggle" not in response.text


@pytest.mark.asyncio
async def test_public_product_galleries_have_visible_navigation():
    service = get_product_service()
    product = await service.create_product(
        ProductCreate(name="Gallery product", category="Tools", featured=True),
        [image_upload(), image_upload("blue")],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        home = await client.get("/")
        detail = await client.get(f"/product/{product.id}")

    assert home.status_code == 200
    assert home.text.index("Featured products") < home.text.index("What we supply")
    assert 'data-card-step="-1"' in home.text
    assert 'data-card-step="1"' in home.text
    assert "View all products" in home.text
    assert detail.status_code == 200
    assert 'data-gallery-step="-1"' in detail.text
    assert 'data-gallery-step="1"' in detail.text


@pytest.mark.asyncio
async def test_featured_products_and_keywords():
    service = get_product_service()
    standard = await service.create_product(
        ProductCreate(name="Standard item", category="Tools", tags="maintenance"), []
    )
    featured = await service.create_product(
        ProductCreate(
            name="Rig handling tool",
            category="Tools",
            tags="pipe control, rig safety",
            featured=True,
        ),
        [],
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        home = await client.get("/")
        search = await client.get("/catalog?q=pipe+control")
        detail = await client.get(f"/product/{featured.id}")

    assert featured.name in home.text
    assert standard.name in home.text
    assert home.text.count('class="card-featured-badge"') == 1
    assert featured.name in search.text
    assert 'name="keywords"' in detail.text
    # Search keywords are for search only and must not be shown to visitors.
    assert "rig safety</span>" not in detail.text
    assert "pipe control" in detail.text


@pytest.mark.asyncio
async def test_edit_respects_total_gallery_limit(monkeypatch):
    service = get_product_service()
    monkeypatch.setattr(service, "max_upload_files", 1)
    product = await service.create_product(ProductCreate(name="Full gallery", category="Tools"), [image_upload()])
    original = product.images[:]
    with pytest.raises(ValidationError, match="up to 1 images"):
        await service.update_product(product.id, ProductUpdate(name="Full gallery", category="Tools"), [image_upload("blue")])
    assert service.get_product(product.id).images == original
    assert all((service.image_service.upload_dir / name).exists() for name in original)
    service.delete_product(product.id)


@pytest.mark.asyncio
async def test_quote_suggestions_match_name_and_category_and_escape_wildcards():
    service = get_product_service()
    await service.create_product(
        ProductCreate(name="Gate valve 2in", category="Valves", tags="api 6d"), []
    )
    await service.create_product(
        ProductCreate(name="Safety gloves", category="PPE", tags=""), []
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        by_name = await client.get("/api/suggest", params={"q": "gate"})
        by_tag = await client.get("/api/suggest", params={"q": "api 6"})
        wildcard = await client.get("/api/suggest", params={"q": "%%"})
        short = await client.get("/api/suggest", params={"q": "g"})
    assert by_name.json()["items"] == [{"name": "Gate valve 2in", "category": "Valves"}]
    assert [item["name"] for item in by_tag.json()["items"]] == ["Gate valve 2in"]
    assert wildcard.json()["items"] == []
    assert short.json()["items"] == []
    assert by_name.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_hostile_product_text_is_escaped_on_every_public_page():
    service = get_product_service()
    payload = '<script>alert(1)</script>"\'<img src=x onerror=alert(2)>'
    product = await service.create_product(
        ProductCreate(
            name=payload,
            category="Tools",
            description=payload,
            specs=[f"{payload}: {payload}"],
            tags=payload,
            featured=True,
        ),
        [],
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        pages = [
            await client.get("/"),
            await client.get("/catalog"),
            await client.get("/catalog", params={"q": payload}),
            await client.get(f"/product/{product.id}"),
        ]
        suggestions = await client.get("/api/suggest", params={"q": "alert"})
    for page in pages:
        assert page.status_code == 200
        assert "<script>alert(1)" not in page.text
        assert "<img src=x onerror" not in page.text
    # The type-ahead returns data, never markup: JSON the browser will not sniff as HTML.
    assert suggestions.headers["content-type"].startswith("application/json")
    assert suggestions.headers["x-content-type-options"] == "nosniff"
    assert suggestions.json()["items"][0]["name"] == payload
