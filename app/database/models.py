from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database.db import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    products = relationship("Product", back_populates="category_ref")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("name", "category", name="uq_product_name_category"),
    )

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, index=True)
    description = Column(Text)
    specs = Column(Text)
    tags = Column(String)
    image = Column(String)
    images = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    category_ref = relationship("Category", back_populates="products")


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    visited_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
