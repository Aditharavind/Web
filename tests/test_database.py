"""Database integrity and migration readiness regression checks."""

from dataclasses import replace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.database import db


def test_sqlite_foreign_keys_are_enforced():
    with db.engine.begin() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO products (id, name, category, category_id) VALUES ('orphan', 'Invalid', 'Missing', 99999)"
                )
            )


@pytest.mark.parametrize("revision", [None, "0001_initial", "0002_indexes", "unknown"])
def test_production_requires_current_migration(monkeypatch, revision):
    engine = create_engine("sqlite://")
    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(db, "settings", replace(db.settings, is_production=True))
    try:
        if revision:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
                    )
                )
                connection.execute(
                    text("INSERT INTO alembic_version VALUES (:revision)"),
                    {"revision": revision},
                )
        if revision == "0002_indexes":
            db.ensure_database_schema()
        else:
            with pytest.raises(RuntimeError, match="alembic upgrade head"):
                db.ensure_database_schema()
    finally:
        engine.dispose()
