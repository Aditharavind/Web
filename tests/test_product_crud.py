import os
import shutil
import tempfile
import uuid

import io
import pytest
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport

from app.main import app
from app.core.config import get_settings
from app.services.dependencies import get_product_service, get_product_service as _gps
from app.services.image_service import ImageService

settings = get_settings()


@pytest.mark.asyncio
async def test_product_crud_and_image_upload(tmp_path):
    # use a temp uploads dir and a temp sqlite DB so the test is isolated
    old_upload_env = os.getenv("UPLOAD_DIR")
    old_db_env = os.getenv("DATABASE_URL")
    os.environ["UPLOAD_DIR"] = str(tmp_path)
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

    # reload config and db modules so settings and engine pick up the temp envs
    from importlib import reload

    reload(__import__("app.core.config", fromlist=["get_settings"]))
    reload(__import__("app.database.db", fromlist=["engine", "Base"]))

    # import/reload models so they register with the (reloaded) Base.metadata
    import app.database.models as models_mod
    from importlib import reload as _reload
    _reload(models_mod)

    # now get engine/Base and create tables in the temporary DB
    from app.database.db import engine, Base
    Base.metadata.create_all(bind=engine)

    # ensure SessionLocal used by services points to our temp engine
    from sqlalchemy.orm import sessionmaker
    import app.database.db as db_mod
    import app.services.product_service as ps_mod

    new_session = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
    # override SessionLocal in both modules to ensure same sessionmaker is used
    db_mod.SessionLocal = new_session
    ps_mod.SessionLocal = new_session

    # reload services so they pick up the new SessionLocal/engine
    reload(__import__("app.services.product_service", fromlist=["ProductService"]))
    reload(__import__("app.services.dependencies", fromlist=["get_product_service"]))

    from app.core.config import get_settings as _get_settings
    local_settings = _get_settings()

    # ensure fresh service factories use the new settings
    from app.services import dependencies as deps

    deps.get_product_service.cache_clear()
    deps.get_visit_service.cache_clear()
    deps.get_session_service.cache_clear()

    product_service = deps.get_product_service()
    image_service = ImageService(local_settings.uploads_dir, local_settings.max_upload_size_bytes, local_settings.image_max_dimension)

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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        r = await ac.get(f"/product/{created.id}")
        assert r.status_code == 200
        assert "Test Product" in r.text

    # cleanup
    await image_service.delete_image(created.images.split(",")[0]) if created.images else None
    # restore envs
    if old_upload_env is None:
        os.environ.pop("UPLOAD_DIR", None)
    else:
        os.environ["UPLOAD_DIR"] = old_upload_env
    if old_db_env is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = old_db_env
    # clear caches to avoid leaking temp settings into other tests
    deps.get_product_service.cache_clear()
    deps.get_visit_service.cache_clear()
    deps.get_session_service.cache_clear()


@pytest.mark.asyncio
async def test_template_rendering_home():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        r = await ac.get("/")
        assert r.status_code == 200
        assert "NAWA Global" in r.text
