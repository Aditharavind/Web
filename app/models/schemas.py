from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProductBase(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = ""
    specs: list[str] = Field(default_factory=list)
    tags: str = ""

    @field_validator("name", "category", mode="before")
    @classmethod
    def validate_required_text(cls, value: object) -> str:
        text = str(value or "").strip().lower()
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
        return [str(item).strip() for item in value if str(item).strip()]


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


class ContactInquiry(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    company: str = ""
    product: str = ""
    message: str = Field(min_length=1)

    @field_validator("name", "message", mode="before")
    @classmethod
    def validate_contact_text(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("This field is required.")
        return text

    @field_validator("company", "product", mode="before")
    @classmethod
    def normalize_contact_optional_text(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text or "@" not in text:
            raise ValueError("A valid email address is required.")
        local, _, domain = text.partition("@")
        if not local or "." not in domain:
            raise ValueError("A valid email address is required.")
        return text


class PaginatedCatalog(BaseModel):
    items: list[Product]
    total: int
    total_pages: int
    page: int
    query: str
    category: str
