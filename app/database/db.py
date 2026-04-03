from __future__ import annotations

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
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


def _ensure_sqlite_schema(connection: Engine) -> None:
    logger.info("SQLite database detected; using SQLAlchemy metadata only.")


def _ensure_postgres_schema() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "products" not in table_names or "categories" not in table_names:
        return

    product_columns = {column["name"] for column in inspector.get_columns("products")}
    category_columns = {column["name"] for column in inspector.get_columns("categories")}

    with engine.begin() as connection:
        if "created_at" not in category_columns:
            connection.execute(text("ALTER TABLE categories ADD COLUMN created_at TIMESTAMP"))
            connection.execute(
                text("UPDATE categories SET created_at = NOW() WHERE created_at IS NULL")
            )
            connection.execute(
                text("ALTER TABLE categories ALTER COLUMN created_at SET NOT NULL")
            )

        if "category_id" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN category_id INTEGER"))

        connection.execute(
            text(
                """
                INSERT INTO categories (name, created_at)
                VALUES ('general', NOW())
                ON CONFLICT (name) DO NOTHING
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE products
                SET category = 'general'
                WHERE category IS NULL OR BTRIM(category) = ''
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE products
                SET name = BTRIM(name)
                WHERE name IS NOT NULL
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE products
                SET category = BTRIM(category)
                WHERE category IS NOT NULL
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO categories (name, created_at)
                SELECT DISTINCT category, NOW()
                FROM products
                WHERE category IS NOT NULL AND BTRIM(category) <> ''
                ON CONFLICT (name) DO NOTHING
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE products
                SET category_id = categories.id
                FROM categories
                WHERE products.category = categories.name
                  AND (products.category_id IS NULL OR products.category_id <> categories.id)
                """
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE products
                ALTER COLUMN category SET NOT NULL
                """
            )
        )
        connection.execute(
            text(
                """
                ALTER TABLE products
                ALTER COLUMN category_id SET NOT NULL
                """
            )
        )

        refreshed_inspector = inspect(connection)
        foreign_keys = {fk["name"] for fk in refreshed_inspector.get_foreign_keys("products")}
        if "fk_products_category_id" not in foreign_keys:
            connection.execute(
                text(
                    """
                    ALTER TABLE products
                    ADD CONSTRAINT fk_products_category_id
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                    """
                )
            )

        unique_constraints = {
            constraint["name"]
            for constraint in refreshed_inspector.get_unique_constraints("products")
        }
        if "uq_product_name_category" not in unique_constraints:
            connection.execute(
                text(
                    """
                    ALTER TABLE products
                    ADD CONSTRAINT uq_product_name_category
                    UNIQUE (name, category)
                    """
                )
            )


def ensure_database_schema() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        if engine.dialect.name == "postgresql":
            _ensure_postgres_schema()
        else:
            _ensure_sqlite_schema(engine)
        logger.info("Database schema is ready.")
    except SQLAlchemyError:
        logger.exception("Database schema initialization failed.")
        raise
