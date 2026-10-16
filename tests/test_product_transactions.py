"""Product writes must release the event loop and roll back related changes."""

import threading

import pytest
from sqlalchemy import event

from app.database.db import engine
from app.models.schemas import ProductCreate, ProductUpdate
from app.services.dependencies import get_product_service
from tests.test_product_crud import image_upload


@pytest.mark.asyncio
async def test_product_database_writes_run_outside_event_loop():
    main_thread = threading.get_ident()
    threads = []

    def record_thread(*args):
        threads.append(threading.get_ident())

    event.listen(engine, "before_cursor_execute", record_thread)
    try:
        service = get_product_service()
        product = await service.create_product(
            ProductCreate(name="Valve", category="Flow"), []
        )
        await service.update_product(
            product.id, ProductUpdate(name="Valve updated", category="Flow"), []
        )
        assert threads
        assert main_thread not in threads
    finally:
        event.remove(engine, "before_cursor_execute", record_thread)


@pytest.mark.asyncio
async def test_failed_product_rolls_back_category_and_files(monkeypatch):
    service = get_product_service()
    before = set(service.image_service.upload_dir.iterdir())
    with monkeypatch.context() as patch:

        def fail_conversion(record):
            raise RuntimeError("conversion failed")

        patch.setattr(service, "_to_product", fail_conversion)
        with pytest.raises(RuntimeError, match="conversion failed"):
            await service.create_product(
                ProductCreate(name="Fail", category="Uncommitted category"),
                [image_upload()],
            )
    assert service.list_products() == []
    assert service.get_categories() == []
    assert set(service.image_service.upload_dir.iterdir()) == before
