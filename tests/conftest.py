import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_TEST_ROOT = tempfile.TemporaryDirectory(prefix="nawa-tests-")
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT.name}/test.db"
os.environ["UPLOAD_DIR"] = f"{_TEST_ROOT.name}/uploads"
os.environ.pop("REDIS_URL", None)

import pytest

from app.core.rate_limiter import _local
from app.database import models  # noqa: F401  (registers tables on Base)
from app.database.db import Base, engine


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.create_all(engine)
    _local.clear()
    yield
    Base.metadata.drop_all(engine)
