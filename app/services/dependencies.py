from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.auth import SessionService
from app.services.image_service import ImageService
from app.services.import_service import ProductImportService
from app.services.product_service import ProductService
from app.services.visit_service import VisitService


@lru_cache(maxsize=1)
def get_product_service() -> ProductService:
    settings = get_settings()
    return ProductService(
        image_service=ImageService(
            settings.uploads_dir,
            max_upload_size_bytes=settings.max_upload_size_bytes,
            image_max_dimension=settings.image_max_dimension,
        ),
        products_per_page=settings.products_per_page,
        max_upload_files=settings.max_upload_files,
    )


@lru_cache(maxsize=1)
def get_import_service() -> ProductImportService:
    product_service = get_product_service()
    return ProductImportService(product_service, product_service.image_service)


@lru_cache(maxsize=1)
def get_visit_service() -> VisitService:
    return VisitService()


@lru_cache(maxsize=1)
def get_session_service() -> SessionService:
    return SessionService(get_settings())
