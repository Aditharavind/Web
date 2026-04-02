from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database.db import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    description = Column(Text)
    specs = Column(Text)
    tags = Column(String)
    image = Column(String)
    images = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    ip = Column(String, nullable=False, index=True)
    visited_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
