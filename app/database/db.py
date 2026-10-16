from __future__ import annotations

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import BASE_DIR, get_settings

settings = get_settings()


def _engine_options(database_url: str) -> dict[str, object]:
    common: dict[str, object] = {
        "pool_pre_ping": True,
        "future": True,
    }
    if database_url.startswith("sqlite"):
        common["connect_args"] = {"check_same_thread": False, "timeout": 5}
        return common

    common.update(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_recycle": 1800,
            "pool_timeout": 10,
        }
    )
    return common


engine = create_engine(settings.database_url, **_engine_options(settings.database_url))


def _configure_sqlite_connection(connection, _record) -> None:
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


if engine.dialect.name == "sqlite":
    event.listen(engine, "connect", _configure_sqlite_connection)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def ensure_database_schema() -> None:
    if settings.is_production:
        config = Config()
        config.set_main_option("script_location", str(BASE_DIR / "alembic"))
        expected = set(ScriptDirectory.from_config(config).get_heads())
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
        if current != expected:
            raise RuntimeError(
                "Database migrations are required. Run alembic upgrade head before starting."
            )
        return
    Base.metadata.create_all(bind=engine)
