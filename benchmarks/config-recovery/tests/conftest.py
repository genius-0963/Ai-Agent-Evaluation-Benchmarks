"""Independent evaluator test fixtures and target service resolution."""

import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def workspace_path() -> Path:
    """Path to the agent workspace being evaluated."""
    raw = os.getenv("EVAL_WORKSPACE_PATH")
    if raw:
        p = Path(raw).resolve()
        if p.is_dir():
            return p
    # Fallback to local task directory
    fallback = Path(__file__).resolve().parent.parent
    return fallback


@pytest.fixture(scope="session")
def client(workspace_path: Path):
    """Test client targeting either a remote container service or the repaired workspace."""
    base_url = os.getenv("EVAL_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=5.0) as http_client:
            yield http_client
        return

    # In-process workspace evaluation
    workspace_str = str(workspace_path)
    if workspace_str not in sys.path:
        sys.path.insert(0, workspace_str)

    # Clean cached modules so fresh workspace code is evaluated
    for mod in list(sys.modules.keys()):
        if mod.startswith("app"):
            sys.modules.pop(mod, None)

    # Set config file to workspace .env
    workspace_env = workspace_path / ".env"
    if workspace_env.is_file():
        os.environ["BENCH_CONFIG_FILE"] = str(workspace_env)
        os.environ.pop("BENCH_CATALOG_ITEMS", None)

    try:
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client
    finally:
        for mod in list(sys.modules.keys()):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)
