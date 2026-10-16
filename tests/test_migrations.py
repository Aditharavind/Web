"""Exercise migration creation and round trips using temporary files only."""

import shutil
import sqlite3

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.core.config import BASE_DIR, get_settings


def test_generated_revision_and_schema_round_trip(tmp_path, monkeypatch):
    scripts = tmp_path / "alembic"
    shutil.copytree(
        BASE_DIR / "alembic", scripts, ignore=shutil.ignore_patterns("__pycache__")
    )
    config = Config()
    config.set_main_option("script_location", str(scripts))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/migration.db")
    get_settings.cache_clear()
    try:
        revision = command.revision(config, message="temporary regression revision")
        assert revision.down_revision == "0003_admin_sessions"
        assert (
            ScriptDirectory.from_config(config).get_current_head() == revision.revision
        )
        command.upgrade(config, "0002_indexes")
        with sqlite3.connect(tmp_path / "migration.db") as db:
            db.execute(
                "INSERT INTO categories (id, name, created_at) VALUES (1, 'Existing', '2026-01-01')"
            )
            db.execute(
                "INSERT INTO products (id, name, category, category_id) VALUES ('keep', 'Keep product', 'Existing', 1)"
            )
        command.upgrade(config, "head")
        with sqlite3.connect(tmp_path / "migration.db") as db:
            assert db.execute(
                "SELECT name FROM products WHERE id='keep'"
            ).fetchone() == ("Keep product",)
            assert db.execute("SELECT COUNT(*) FROM admin_sessions").fetchone()[0] == 0
        command.check(config)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        get_settings.cache_clear()
