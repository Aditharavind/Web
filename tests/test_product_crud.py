import io

import pytest
from PIL import Image
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.schemas import ProductCreate, ProductUpdate
from app.services.dependencies import get_product_service
from app.core.exceptions import ValidationError


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
