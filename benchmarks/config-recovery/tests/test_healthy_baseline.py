import os

import pytest
from fastapi.testclient import TestClient

# Ensure no broken env file is loaded for baseline tests
os.environ.pop("BENCH_CATALOG_ITEMS", None)
os.environ["BENCH_CONFIG_FILE"] = "/dev/null"

import sys
from pathlib import Path

# Add app parent directory to sys.path so 'app.main' resolves
app_dir = Path(__file__).resolve().parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_catalog(client):
    response = client.get("/api/catalog")
    assert response.status_code == 200
    assert response.json() == {"items": ["alpha", "beta"]}
