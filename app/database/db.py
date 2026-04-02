from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://nawa_global_user:cpkSm5wj203w0hgohqDGZ8DmSTMj7got@dpg-d775pc7afjfc73d9elo0-a/nawa_global")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_postgres_schema() -> None:
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
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
                SET name = LOWER(BTRIM(name))
                WHERE name IS NOT NULL
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
                SET category = LOWER(BTRIM(category))
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
