from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import relationship

from app.database.db import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
    )

    products = relationship("Product", back_populates="category_ref")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("name", "category", name="uq_product_name_category"),
    )

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    category_id = Column(
        Integer, ForeignKey("categories.id"), nullable=False, index=True
    )
    description = Column(Text)
    specs = Column(Text)
    tags = Column(String)
    image = Column(String)
    images = Column(Text)
    is_featured = Column(
        Boolean, nullable=False, default=False, server_default=false(), index=True
    )
    created_at = Column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    category_ref = relationship("Category", back_populates="products")


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    visited_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC).replace(tzinfo=None),
        nullable=False,
        index=True,
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    token_hash = Column(String(64), primary_key=True)
    expires_at = Column(BigInteger, nullable=False, index=True)
