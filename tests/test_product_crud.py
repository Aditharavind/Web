import os
import shutil
import tempfile
import uuid

import io
import pytest
from httpx import AsyncClient

from app.main import app
from app.core.config import get_settings
from app.services.dependencies import get_product_service, get_product_service as _gps
from app.services.image_service import ImageService

settings = get_settings()


@pytest.mark.asyncio
async def test_product_crud_and_image_upload(tmp_path):
    # use a temp uploads dir
    old_upload = settings.uploads_dir
    settings.uploads_dir = tmp_path

    product_service = get_product_service()
    image_service = ImageService(settings.uploads_dir, settings.max_upload_size_bytes, settings.image_max_dimension)

    # create a sample in-memory image
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    class DummyUpload:
        def __init__(self, filename, content):
            self.filename = filename
            self._content = content

        async def read(self):
            return self._content

    upload = DummyUpload("test.jpg", buf.getvalue())

    # create product via service
    from app.models.schemas import ProductCreate

    payload = ProductCreate(
        name="Test Product",
        category="Testing",
        description="A test product",
        specs=["Size:Small"],
        tags="test",
    )

    created = await product_service.create_product(payload, [upload])

    assert created.name == "Test Product"
    assert created.images

    # fetch via public endpoint
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        r = await ac.get(f"/product/{created.id}")
        assert r.status_code == 200
        assert "Test Product" in r.text

    # cleanup
    await image_service.delete_image(created.images.split(",")[0]) if created.images else None
    settings.uploads_dir = old_upload


@pytest.mark.asyncio
async def test_template_rendering_home():
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        r = await ac.get("/")
        assert r.status_code == 200
        assert "NAWA Global" in r.text
