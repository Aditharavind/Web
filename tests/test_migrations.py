"""Exercise migration creation and round trips using temporary files only."""

import shutil

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
        assert revision.down_revision == "0002_indexes"
        assert (
            ScriptDirectory.from_config(config).get_current_head() == revision.revision
        )
        command.upgrade(config, "head")
        command.check(config)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        get_settings.cache_clear()
