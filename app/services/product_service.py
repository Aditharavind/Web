from __future__ import annotations

import math
import uuid
from datetime import datetime

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.core.exceptions import DuplicateProductError, ProductNotFoundError, ValidationError
from app.database.db import SessionLocal
from app.database.models import Category, Product
from app.models.schemas import PaginatedCatalog, Product as ProductSchema, ProductCreate, ProductUpdate
from app.services.image_service import ImageService


class ProductService:
    def __init__(self, image_service: ImageService, products_per_page: int) -> None:
        self.image_service = image_service
        self.products_per_page = products_per_page

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
    def _normalize_text(value: str | None) -> str:
        return str(value or "").strip().lower()

    def _get_or_create_category(self, db, category_name: str) -> Category:
        normalized_category = self._normalize_text(category_name)
        if not normalized_category:
            raise ValidationError("This field is required.")

        category = (
            db.query(Category)
            .filter(Category.name == normalized_category)
            .first()
        )
        if category is not None:
            return category

        category = Category(name=normalized_category)
        db.add(category)
        try:
            db.commit()
            db.refresh(category)
            return category
        except IntegrityError:
            db.rollback()
            category = (
                db.query(Category)
                .filter(Category.name == normalized_category)
                .first()
            )
            if category is None:
                raise ValidationError("Unable to save category")
            return category

    async def _save_images(self, product_id: str, images: list[UploadFile]) -> list[str]:
        saved: list[str] = []
        index = 0
        for image in images:
            if not (image.filename or "").strip():
                continue
            suffix = "" if index == 0 else f"-{index + 1}"
            saved.append(await self.image_service.save_image(image, product_id, suffix))
            index += 1
        return saved

    def list_products(self) -> list[ProductSchema]:
        db = SessionLocal()
        try:
            records = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .order_by(Product.created_at.desc())
                .all()
            )
            return [self._to_product(record) for record in records]
        finally:
            db.close()

    def get_product(self, product_id: str) -> ProductSchema:
        db = SessionLocal()
        try:
            record = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .filter(Product.id == product_id)
                .first()
            )
            if record is None:
                raise ProductNotFoundError("Product not found")
            return self._to_product(record)
        finally:
            db.close()

    def recent_products(self, limit: int) -> list[ProductSchema]:
        db = SessionLocal()
        try:
            records = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .order_by(Product.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._to_product(record) for record in records]
        finally:
            db.close()

    def get_categories(self) -> list[str]:
        db = SessionLocal()
        try:
            records = db.query(Category).order_by(Category.name.asc()).all()
            return [record.name.strip() for record in records if record.name.strip()]
        finally:
            db.close()

    def search_catalog(self, page: int, query: str, category: str) -> PaginatedCatalog:
        db = SessionLocal()
        try:
            normalized_page = max(1, page)
            normalized_query = query.strip().lower()
            normalized_category = category.strip().lower()

            db_query = db.query(Product).options(joinedload(Product.category_ref))

            if normalized_query:
                like = f"%{normalized_query}%"
                db_query = db_query.filter(
                    (Product.name.ilike(like))
                    | (Product.description.ilike(like))
                    | (Product.tags.ilike(like))
                    | (Product.category.ilike(like))
                )

            if normalized_category:
                db_query = db_query.filter(Product.category == normalized_category)

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
                query=normalized_query,
                category=normalized_category,
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

    async def create_product(self, payload: ProductCreate, images: list[UploadFile]) -> ProductSchema:
        db = SessionLocal()
        try:
            normalized_name = self._normalize_text(payload.name)
            normalized_category = self._normalize_text(payload.category)
            category = self._get_or_create_category(db, normalized_category)

            existing = db.query(Product).filter(
                Product.name == normalized_name,
                Product.category == normalized_category,
            ).first()
            if existing is not None:
                raise DuplicateProductError("Product already exists")

            product_id = str(uuid.uuid4())[:8]
            saved_images = await self._save_images(product_id, images)

            record = Product(
                id=product_id,
                name=normalized_name,
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
            except IntegrityError:
                db.rollback()
                raise DuplicateProductError("Product already exists")
            return self._to_product(record)
        finally:
            db.close()

    async def update_product(
        self,
        product_id: str,
        payload: ProductUpdate,
        images: list[UploadFile],
    ) -> ProductSchema:
        db = SessionLocal()
        try:
            record = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .filter(Product.id == product_id)
                .first()
            )
            if record is None:
                raise ProductNotFoundError("Product not found")

            normalized_name = self._normalize_text(payload.name)
            normalized_category = self._normalize_text(payload.category)
            category = self._get_or_create_category(db, normalized_category)
            duplicate = db.query(Product).filter(
                Product.id != product_id,
                Product.name == normalized_name,
                Product.category == normalized_category,
            ).first()
            if duplicate is not None:
                raise DuplicateProductError("Product already exists")

            existing_images = self._split_images(record.images)
            new_images = await self._save_images(product_id, images)
            combined_images = existing_images + new_images

            record.name = normalized_name
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
            except IntegrityError:
                db.rollback()
                raise DuplicateProductError("Product already exists")
            fresh_record = (
                db.query(Product)
                .options(joinedload(Product.category_ref))
                .filter(Product.id == product_id)
                .first()
            )
            if fresh_record is None:
                raise ProductNotFoundError("Product not found")
            return self._to_product(fresh_record)
        finally:
            db.close()

    def delete_product_image(self, product_id: str, filename: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found")

            existing_images = self._split_images(record.images)
            images = [image for image in existing_images if image != filename]
            if len(images) != len(existing_images):
                self.image_service.delete_image(filename)

            record.image = images[0] if images else None
            record.images = self._join_images(images)

            db.add(record)
            db.commit()
        finally:
            db.close()

    def delete_product(self, product_id: str) -> None:
        db = SessionLocal()
        try:
            record = db.query(Product).filter(Product.id == product_id).first()
            if record is None:
                raise ProductNotFoundError("Product not found")

            for image in self._split_images(record.images):
                self.image_service.delete_image(image)

            db.delete(record)
            db.commit()
        finally:
            db.close()
