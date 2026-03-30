import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_STORAGE_DIR = Path(tempfile.mkdtemp(prefix="preguntalo-storage-"))
_DB_DIR = Path(tempfile.mkdtemp(prefix="preguntalo-db-"))
_DB_FILE = _DB_DIR / "preguntalo.db"

os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_DB_FILE}?check_same_thread=False")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("LOCAL_STORAGE_ROOT", str(_STORAGE_DIR))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("S3_BUCKET", "manuals")

from app.main import app  # noqa: E402
from app.workers.ingestion import IngestionWorker  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def ingestion_worker() -> IngestionWorker:
    return IngestionWorker()
