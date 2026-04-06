from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime

from fastapi import UploadFile, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

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
    Product as ProductSchema,
    ProductCreate,
    ProductUpdate,
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
            image=record.image or (images[0] if images else None),
            images=images,
            created=record.created_at or datetime.utcnow(),
        )

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return str(value or "").strip()

    @classmethod
    def _normalize_text(cls, value: str | None) -> str:
        return cls._clean_text(value).casefold()

    def _validate_image_count(self, images: list[UploadFile] | list[tuple[str, bytes]]) -> None:
        # images may be UploadFile list or pre-read list of (filename, bytes)
        if images and isinstance(images[0], tuple):
            actual_uploads = [img for img in images if (img[0] or "").strip()]
        else:
            actual_uploads = [image for image in images if (image.filename or "").strip()]
        if len(actual_uploads) > self.max_upload_files:
            raise ValidationError(f"You can upload up to {self.max_upload_files} images per product.")

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
        db.add(category)
        try:
            db.commit()
            db.refresh(category)
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

    async def _save_images(self, product_id: str, images: list[UploadFile], background: BackgroundTasks | None) -> list[str]:
        """
        Read UploadFile objects into bytes, validate count, and schedule background processing.
        Returns list of filenames that will be stored (placeholder names).
        """
        self._validate_image_count(images)
        # read payloads in async context (non-blocking) then process in background
        read_images: list[tuple[str, bytes]] = []
        for image in images:
            if not (image.filename or "").strip():
                continue
            payload = await image.read()
            read_images.append((image.filename or "", payload))

        if not read_images:
            return []

        # generate filenames that will be created (deterministic)
        filenames: list[str] = []
        for idx in range(len(read_images)):
            suffix = "" if idx == 0 else f"-{idx + 1}"
            filenames.append(f"{product_id}{suffix}.jpg")

        # schedule background processing to run sync image work in worker
        if background is not None:
            background.add_task(self.image_service.process_and_store_images, product_id, read_images)
        else:
            # fallback: process synchronously (should not happen in async endpoints)
            self.image_service.process_and_store_images(product_id, read_images)

        return filenames

    def _list_products_sync(self) -> list[Product]:
        db = SessionLocal()
        try:
            records = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .order_by(Product.created_at.desc())
                .all()
            )
            return records
        finally:
            db.close()

    def list_products(self) -> list[ProductSchema]:
        records = self._list_products_sync()
        return [self._to_product(record) for record in records]

    def _get_product_sync(self, product_id: str) -> Product | None:
        db = SessionLocal()
        try:
            return (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .filter(Product.id == product_id)
                .first()
            )
        finally:
            db.close()

    def get_product(self, product_id: str) -> ProductSchema:
        record = self._get_product_sync(product_id)
        if record is None:
            raise ProductNotFoundError("Product not found.")
        return self._to_product(record)

    def _recent_products_sync(self, limit: int) -> list[Product]:
        db = SessionLocal()
        try:
            return (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .order_by(Product.created_at.desc())
                .limit(limit)
                .all()
            )
        finally:
            db.close()

    def recent_products(self, limit: int) -> list[ProductSchema]:
        records = self._recent_products_sync(limit)
        return [self._to_product(record) for record in records]

    def get_categories(self) -> list[str]:
        db = SessionLocal()
        try:
            records = db.query(Category).order_by(Category.name.asc()).all()
            return [record.name.strip() for record in records if record.name.strip()]
        finally:
            db.close()

    def search_catalog(self, page: int, query: str, category: str) -> PaginatedCatalog:
        """
        Synchronous pagination logic. This method is safe to call from async endpoints
        when executed via run_in_threadpool at the route level.
        """
        db = SessionLocal()
        try:
            normalized_page = max(1, page)
            raw_query = query.strip()
            raw_category = category.strip()
            normalized_query = raw_query.casefold()
            normalized_category = raw_category.casefold()

            db_query = db.query(Product).options(joinedload(Product.category_ref))

            if normalized_query:
                like = f"%{normalized_query}%"
                db_query = db_query.filter(
                    Product.name.ilike(like)
                    | Product.description.ilike(like)
                    | Product.tags.ilike(like)
                    | Product.category.ilike(like)
                )

            if normalized_category:
                db_query = db_query.filter(func.lower(Product.category) == normalized_category)

            total = db_query.count()
            total_pages = max(1, math.ceil(total / self.products_per_page)) if total else 1
            current_page = min(normalized_page, total_pages)
            offset = (current_page - 1) * self.products_per_page

            records = (
                db_query
                .order_by(Product.created_at.desc())
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
                category=raw_category,
            )
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
        self,
        payload: ProductCreate,
        images: list[UploadFile],
        background: BackgroundTasks | None = None,
    ) -> ProductSchema:
        """
        Async-friendly create. Heavy image processing is scheduled in background tasks.
        DB interactions remain synchronous and are safe because endpoints should call this via run_in_threadpool
        when used from async routes.
        """
        # basic validations and category resolution performed synchronously using a dedicated session
        # validate and read images in async context
        cleaned_name = self._clean_text(payload.name)
        cleaned_category = self._clean_text(payload.category)
        normalized_name = self._normalize_text(cleaned_name)
        normalized_category = self._normalize_text(cleaned_category)

        product_id = str(uuid.uuid4())[:8]
        saved_images = await self._save_images(product_id, images, background)

        # perform DB write in threadpool to avoid blocking the event loop
        try:
            record = await run_in_threadpool(
                self._create_product_sync,
                product_id,
                cleaned_name,
                cleaned_category,
                payload,
                saved_images,
            )
            return self._to_product(record)
        except DuplicateProductError:
            for filename in saved_images:
                self.image_service.delete_image(filename)
            raise
        except SQLAlchemyError as exc:
            for filename in saved_images:
                self.image_service.delete_image(filename)
            logger.exception("Failed to create product.")
            raise DataAccessError("Unable to save the product right now.") from exc

    def _create_product_sync(
        self,
        product_id: str,
        cleaned_name: str,
        cleaned_category: str,
        payload: ProductCreate,
        saved_images: list[str],
    ) -> Product:
        db = SessionLocal()
        try:
            category = self._get_or_create_category(db, cleaned_category)

            normalized_name = self._normalize_text(cleaned_name)
            normalized_category = self._normalize_text(cleaned_category)
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
                image=saved_images[0] if saved_images else None,
                images=self._join_images(saved_images),
            )
            db.add(record)
            try:
                db.commit()
                db.refresh(record)
            except IntegrityError as exc:
                db.rollback()
                raise DuplicateProductError("Product already exists.") from exc
            return record
        finally:
            db.close()

    async def update_product(
        self,
        product_id: str,
        payload: ProductUpdate,
        images: list[UploadFile],
        background: BackgroundTasks | None = None,
    ) -> ProductSchema:
        # read new images and schedule processing
        saved_images = await self._save_images(product_id, images, background)

        try:
            record = await run_in_threadpool(
                self._update_product_sync, product_id, payload, saved_images
            )
            return self._to_product(record)
        except (DuplicateProductError, ProductNotFoundError, ValidationError):
            for filename in saved_images:
                self.image_service.delete_image(filename)
            raise
        except SQLAlchemyError as exc:
            for filename in saved_images:
                self.image_service.delete_image(filename)
            logger.exception("Failed to update product %s.", product_id)
            raise DataAccessError("Unable to update the product right now.") from exc

    def _update_product_sync(self, product_id: str, payload: ProductUpdate, saved_images: list[str]) -> Product:
        db = SessionLocal()
        try:
            record = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .filter(Product.id == product_id)
                .first()
            )
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

            existing_images = self._split_images(record.images)
            combined_images = existing_images + saved_images

            record.name = cleaned_name
            record.category = category.name
            record.category_id = category.id
            record.description = payload.description
            record.specs = self._join_specs(payload.specs)
            record.tags = payload.tags
            record.image = combined_images[0] if combined_images else None
            record.images = self._join_images(combined_images)

            db.add(record)
            try:
                db.commit()
                db.refresh(record)
            except IntegrityError as exc:
                db.rollback()
                raise DuplicateProductError("Product already exists.") from exc

            fresh_record = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .filter(Product.id == product_id)
                .first()
            )
            if fresh_record is None:
                raise ProductNotFoundError("Product not found.")
            return fresh_record
        finally:
            db.close()

    def delete_product_image(self, product_id: str, filename: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")

            safe_filename = filename.strip()
            existing_images = self._split_images(record.images)
            images = [image for image in existing_images if image != safe_filename]
            if len(images) == len(existing_images):
                raise ValidationError("Image not found.")

            self.image_service.delete_image(safe_filename)
            record.image = images[0] if images else None
            record.images = self._join_images(images)
            db.add(record)
            db.commit()
        except (ProductNotFoundError, ValidationError):
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to delete image %s for product %s.", filename, product_id)
            raise DataAccessError("Unable to delete the image right now.") from exc
        finally:
            db.close()

    def delete_product(self, product_id: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found.")

            for image in self._split_images(record.images):
                self.image_service.delete_image(image)

            db.delete(record)
            db.commit()
        except ProductNotFoundError:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to delete product %s.", product_id)
            raise DataAccessError("Unable to delete the product right now.") from exc
        finally:
            db.close()
