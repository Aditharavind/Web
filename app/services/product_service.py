from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import (
    DataAccessError,
    DuplicateProductError,
    ProductNotFoundError,
    ValidationError,
)
from app.database.db import SessionLocal
from app.database.models import Category, Product
from app.models.schemas import (
    PaginatedCatalog,
    ProductCreate,
    ProductUpdate,
)
from app.models.schemas import (
    Product as ProductSchema,
)
from app.services.image_service import ImageService

logger = logging.getLogger(__name__)


class ProductService:
    def __init__(
        self,
        image_service: ImageService,
        products_per_page: int,
        max_upload_files: int,
    ) -> None:
        self.image_service = image_service
        self.products_per_page = products_per_page
        self.max_upload_files = max_upload_files

    @staticmethod
    def _split_specs(specs: str | list[str] | None) -> list[str]:
        if isinstance(specs, list):
            return [str(item).strip() for item in specs if str(item).strip()]
        if not specs:
            return []
        return [line.strip() for line in str(specs).splitlines() if line.strip()]

    @staticmethod
    def _split_images(images: str | list[str] | None) -> list[str]:
        if isinstance(images, list):
            return [str(item).strip() for item in images if str(item).strip()]
        if not images:
            return []
        return [item.strip() for item in str(images).split(",") if item.strip()]

    @staticmethod
    def _join_specs(specs: list[str] | None) -> str:
        if not specs:
            return ""
        return "\n".join(item.strip() for item in specs if item.strip())

    @staticmethod
    def _join_images(images: list[str] | None) -> str:
        if not images:
            return ""
        return ",".join(item.strip() for item in images if item.strip())

    def _to_product(self, record: Product) -> ProductSchema:
        name = (record.name or "").strip()
        category = (record.category or "").strip()
        description = (record.description or "").strip()
        specs = self._split_specs(record.specs)
        tags = (record.tags or "").strip()
        images = self._split_images(record.images)
        return ProductSchema(
            id=record.id,
            name=name,
            category=category,
            description=description,
            specs=specs,
            tags=tags,
            featured=bool(record.is_featured),
            image=record.image or (images[0] if images else None),
            images=images,
            created=record.created_at
            or datetime.now(timezone.utc).replace(tzinfo=None),
        )

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return str(value or "").strip()

    @classmethod
    def _normalize_text(cls, value: str | None) -> str:
        return cls._clean_text(value).casefold()

    def _validate_image_count(self, images: list[UploadFile]) -> None:
        actual_uploads = [image for image in images if (image.filename or "").strip()]
        if len(actual_uploads) > self.max_upload_files:
            raise ValidationError(
                f"You can upload up to {self.max_upload_files} images per product."
            )

    def _get_or_create_category(self, db, category_name: str) -> Category:
        cleaned_category = self._clean_text(category_name)
        if not cleaned_category:
            raise ValidationError("Category is required.")

        category = (
            db.query(Category)
            .filter(func.lower(Category.name) == cleaned_category.casefold())
            .first()
        )
        if category is not None:
            return category

        category = Category(name=cleaned_category)
        try:
            db.add(category)
            db.flush()
            return category
        except IntegrityError:
            db.rollback()
            category = (
                db.query(Category)
                .filter(func.lower(Category.name) == cleaned_category.casefold())
                .first()
            )
            if category is None:
                raise DataAccessError("Unable to save category.")
            return category

    async def _save_images(
        self, product_id: str, images: list[UploadFile]
    ) -> list[str]:
        self._validate_image_count(images)
        saved: list[str] = []
        try:
            for index, image in enumerate(images):
                if not (image.filename or "").strip():
                    continue
                saved.append(
                    await self.image_service.save_image(image, product_id, f"-{index}")
                )
            return saved
        except Exception:
            for filename in saved:
                self.image_service.delete_image(filename)
            raise

    def counts(self) -> dict[str, int]:
        with SessionLocal() as db:
            return {
                "products": db.query(Product).count(),
                "categories": db.query(Category).count(),
            }

    def list_products(self) -> list[ProductSchema]:
        db = SessionLocal()
        try:
            records = db.query(Product).order_by(Product.created_at.desc()).all()
            return [self._to_product(record) for record in records]
        except SQLAlchemyError as exc:
            logger.exception("Failed to list products.")
            raise DataAccessError("Unable to load products right now.") from exc
        finally:
            db.close()

    def list_product_ids(self) -> list[str]:
        try:
            with SessionLocal() as db:
                return [
                    row[0] for row in db.query(Product.id).order_by(Product.id).all()
                ]
        except SQLAlchemyError as exc:
            raise DataAccessError("Unable to load product links right now.") from exc

    def get_product(self, product_id: str) -> ProductSchema:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")
            return self._to_product(record)
        except SQLAlchemyError as exc:
            logger.exception("Failed to get product %s.", product_id)
            raise DataAccessError("Unable to load the product right now.") from exc
        finally:
            db.close()

    def homepage_products(self, limit: int) -> list[ProductSchema]:
        db = SessionLocal()
        try:
            records = (
                db.query(Product)
                .order_by(Product.is_featured.desc(), Product.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_product(record) for record in records]
        except SQLAlchemyError as exc:
            logger.exception("Failed to load homepage products.")
            raise DataAccessError("Unable to load products right now.") from exc
        finally:
            db.close()

    def get_categories(self) -> list[str]:
        db = SessionLocal()
        try:
            records = db.query(Category).order_by(Category.name.asc()).all()
            return [record.name.strip() for record in records if record.name.strip()]
        except SQLAlchemyError as exc:
            logger.exception("Failed to load categories.")
            raise DataAccessError("Unable to load categories right now.") from exc
        finally:
            db.close()

    def search_catalog(
        self, page: int, query: str, category: str | list[str] = ""
    ) -> PaginatedCatalog:
        db = SessionLocal()
        try:
            normalized_page = max(1, page)
            raw_query = query.strip()
            raw_categories = list(
                dict.fromkeys(
                    item.strip()
                    for item in ([category] if isinstance(category, str) else category)
                    if item and item.strip()
                )
            )
            normalized_query = raw_query.casefold()
            normalized_categories = [item.casefold() for item in raw_categories]

            db_query = db.query(Product)

            if normalized_query:
                like = f"%{normalized_query}%"
                db_query = db_query.filter(
                    Product.name.ilike(like)
                    | Product.description.ilike(like)
                    | Product.tags.ilike(like)
                    | Product.category.ilike(like)
                )

            if normalized_categories:
                db_query = db_query.filter(
                    func.lower(Product.category).in_(normalized_categories)
                )

            total = db_query.count()
            total_pages = (
                max(1, math.ceil(total / self.products_per_page)) if total else 1
            )
            current_page = min(normalized_page, total_pages)
            offset = (current_page - 1) * self.products_per_page

            records = (
                db_query.order_by(Product.created_at.desc())
                .offset(offset)
                .limit(self.products_per_page)
                .all()
            )

            return PaginatedCatalog(
                items=[self._to_product(record) for record in records],
                total=total,
                total_pages=total_pages,
                page=current_page,
                query=raw_query,
                category=", ".join(raw_categories),
                categories=raw_categories,
            )
        except SQLAlchemyError as exc:
            logger.exception("Failed to search catalog.")
            raise DataAccessError("Unable to search the catalog right now.") from exc
        finally:
            db.close()

    def get_product_images(self, product: ProductSchema) -> list[str]:
        images = self._split_images(product.images)
        if images:
            return images
        if product.image:
            return [product.image]
        return []

    async def create_product(
        self, payload: ProductCreate, images: list[UploadFile]
    ) -> ProductSchema:
        product_id = uuid.uuid4().hex
        saved_images = await self._save_images(product_id, images)
        return await run_in_threadpool(
            self._create_product, product_id, payload, saved_images
        )

    def _create_product(
        self, product_id: str, payload: ProductCreate, saved_images: list[str]
    ) -> ProductSchema:
        db = SessionLocal()
        try:
            cleaned_name = self._clean_text(payload.name)
            cleaned_category = self._clean_text(payload.category)
            normalized_name = self._normalize_text(cleaned_name)
            normalized_category = self._normalize_text(cleaned_category)
            category = self._get_or_create_category(db, cleaned_category)

            existing = (
                db.query(Product)
                .filter(
                    func.lower(Product.name) == normalized_name,
                    func.lower(Product.category) == normalized_category,
                )
                .first()
            )
            if existing is not None:
                raise DuplicateProductError("Product already exists.")

            record = Product(
                id=product_id,
                name=cleaned_name,
                category=category.name,
                category_id=category.id,
                description=payload.description,
                specs=self._join_specs(payload.specs),
                tags=payload.tags,
                is_featured=payload.featured,
                image=saved_images[0] if saved_images else None,
                images=self._join_images(saved_images),
            )

            db.add(record)
            try:
                db.flush()
                result = self._to_product(record)
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise DuplicateProductError("Product already exists.") from exc
            return result
        except (DuplicateProductError, ValidationError):
            for filename in saved_images:
                self.image_service.delete_image(filename)
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            for filename in saved_images:
                self.image_service.delete_image(filename)
            logger.exception("Failed to create product.")
            raise DataAccessError("Unable to save the product right now.") from exc
        except Exception:
            db.rollback()
            for filename in saved_images:
                self.image_service.delete_image(filename)
            raise
        finally:
            db.close()

    async def update_product(
        self, product_id: str, payload: ProductUpdate, images: list[UploadFile]
    ) -> ProductSchema:
        saved_images = await self._save_images(product_id, images)
        return await run_in_threadpool(
            self._update_product, product_id, payload, saved_images
        )

    def _update_product(
        self, product_id: str, payload: ProductUpdate, saved_images: list[str]
    ) -> ProductSchema:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")

            cleaned_name = self._clean_text(payload.name)
            cleaned_category = self._clean_text(payload.category)
            normalized_name = self._normalize_text(cleaned_name)
            normalized_category = self._normalize_text(cleaned_category)
            category = self._get_or_create_category(db, cleaned_category)
            duplicate = (
                db.query(Product)
                .filter(
                    Product.id != product_id,
                    func.lower(Product.name) == normalized_name,
                    func.lower(Product.category) == normalized_category,
                )
                .first()
            )
            if duplicate is not None:
                raise DuplicateProductError("Product already exists.")

            existing_images = self._split_images(record.images) or (
                [record.image] if record.image else []
            )
            incoming_count = len(saved_images)
            if len(existing_images) + incoming_count > self.max_upload_files:
                raise ValidationError(
                    f"A product can have up to {self.max_upload_files} images. Remove an existing image before adding more."
                )
            combined_images = existing_images + saved_images

            record.name = cleaned_name
            record.category = category.name
            record.category_id = category.id
            record.description = payload.description
            record.specs = self._join_specs(payload.specs)
            record.tags = payload.tags
            record.is_featured = payload.featured
            record.image = combined_images[0] if combined_images else None
            record.images = self._join_images(combined_images)

            db.add(record)
            try:
                db.flush()
                result = self._to_product(record)
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise DuplicateProductError("Product already exists.") from exc

            return result
        except (DuplicateProductError, ProductNotFoundError, ValidationError):
            for filename in saved_images:
                self.image_service.delete_image(filename)
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            for filename in saved_images:
                self.image_service.delete_image(filename)
            logger.exception("Failed to update product %s.", product_id)
            raise DataAccessError("Unable to update the product right now.") from exc
        except Exception:
            db.rollback()
            for filename in saved_images:
                self.image_service.delete_image(filename)
            raise
        finally:
            db.close()

    def delete_product_image(self, product_id: str, filename: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")

            safe_filename = filename.strip()
            existing_images = self._split_images(record.images) or (
                [record.image] if record.image else []
            )
            images = [image for image in existing_images if image != safe_filename]
            if len(images) == len(existing_images):
                raise ValidationError("Image not found.")

            record.image = images[0] if images else None
            record.images = self._join_images(images)
            db.add(record)
            db.commit()
            self.image_service.delete_image(safe_filename)
        except (ProductNotFoundError, ValidationError):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception(
                "Failed to delete image %s for product %s.", filename, product_id
            )
            raise DataAccessError("Unable to delete the image right now.") from exc
        finally:
            db.close()

    def set_primary_image(self, product_id: str, filename: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")

            safe_filename = filename.strip()
            images = self._split_images(record.images) or (
                [record.image] if record.image else []
            )
            if safe_filename not in images:
                raise ValidationError("Image not found.")

            images = [safe_filename] + [item for item in images if item != safe_filename]
            record.image = images[0]
            record.images = self._join_images(images)
            db.add(record)
            db.commit()
        except (ProductNotFoundError, ValidationError):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to set primary image for product %s.", product_id)
            raise DataAccessError("Unable to update the image right now.") from exc
        finally:
            db.close()

    def delete_product(self, product_id: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")

            images = self._split_images(record.images) or (
                [record.image] if record.image else []
            )
            db.delete(record)
            db.commit()
            for image in images:
                self.image_service.delete_image(image)
        except ProductNotFoundError:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to delete product %s.", product_id)
            raise DataAccessError("Unable to delete the product right now.") from exc
        finally:
            db.close()
