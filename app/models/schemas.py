from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

MAX_TEXT_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 4000
MAX_TAGS_LENGTH = 2000


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    category: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)
    specs: list[str] = Field(default_factory=list, max_length=50)
    tags: str = Field(default="", max_length=MAX_TAGS_LENGTH)
    featured: bool = False

    @field_validator("name", "category", mode="before")
    @classmethod
    def validate_required_text(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("This field must be text.")
        text = value.strip()
        if not text:
            raise ValueError("This field is required.")
        return text

    @field_validator("description", "tags", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("This field must be text.")
        return value.strip()

    @field_validator("specs", mode="before")
    @classmethod
    def normalize_specs(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("Specifications must be a list.")
        if any(not isinstance(item, str) for item in value):
            raise ValueError("Specifications must contain text only.")
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) > 50:
            raise ValueError("No more than 50 specifications are allowed.")
        return cleaned


class Product(ProductBase):
    id: str
    image: str | None = None
    images: list[str] = Field(default_factory=list)
    created: datetime


class ProductCreate(ProductBase):
    # Bound submitted rows while allowing existing longer descriptions to render.
    specs: list[Annotated[str, Field(max_length=MAX_DESCRIPTION_LENGTH)]] = Field(
        default_factory=list, max_length=50
    )


class ProductUpdate(ProductCreate):
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
    categories: list[str] = Field(default_factory=list)
