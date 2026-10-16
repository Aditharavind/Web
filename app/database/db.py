from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


def _engine_options(database_url: str) -> dict[str, object]:
    common: dict[str, object] = {
        "pool_pre_ping": True,
        "future": True,
    }
    if database_url.startswith("sqlite"):
        common["connect_args"] = {"check_same_thread": False}
        return common

    common.update(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 1800,
        }
    )
    return common


engine = create_engine(settings.database_url, **_engine_options(settings.database_url))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def ensure_database_schema() -> None:
    if settings.is_production:
        with engine.connect() as connection:
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if current != "0002_indexes":
            raise RuntimeError("Database migrations are required. Run alembic upgrade head before starting.")
        return
    Base.metadata.create_all(bind=engine)
