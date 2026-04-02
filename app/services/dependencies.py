from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.auth import SessionService
from app.services.image_service import ImageService
from app.services.product_service import ProductService
from app.services.visit_service import VisitService


@lru_cache
def get_product_service() -> ProductService:
    settings = get_settings()
    return ProductService(
        image_service=ImageService(settings.uploads_dir),
        products_per_page=settings.products_per_page,
    )


@lru_cache
def get_visit_service() -> VisitService:
    return VisitService()


@lru_cache
def get_session_service() -> SessionService:
    return SessionService(get_settings())
