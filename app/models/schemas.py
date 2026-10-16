from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


MAX_TEXT_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 4000




class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    category: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    specs: list[str] = Field(default_factory=list, max_length=50)
    tags: str = Field(default="", max_length=MAX_TEXT_LENGTH)

    @field_validator("name", "category", mode="before")
    @classmethod
    def validate_required_text(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("This field is required.")
        return text

    @field_validator("description", "tags", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("specs", mode="before")
    @classmethod
    def normalize_specs(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Specifications must be a list.")
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) > 50:
            raise ValueError("No more than 50 specifications are allowed.")
        return cleaned


class Product(ProductBase):
    id: str
    image: Optional[str] = None
    images: list[str] = Field(default_factory=list)
    created: datetime


class ProductCreate(ProductBase):
    pass


class ProductUpdate(ProductBase):
    pass


class Visit(BaseModel):
    ip: str
    time: datetime


class PaginatedCatalog(BaseModel):
    items: list[Product]
    total: int
    total_pages: int
    page: int
    query: str
    category: str
