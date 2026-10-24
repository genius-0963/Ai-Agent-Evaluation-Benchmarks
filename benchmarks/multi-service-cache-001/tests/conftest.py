"""Independent evaluator fixtures for multi-service cache benchmark."""

import os
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def workspace_path() -> Path:
    raw = os.getenv("EVAL_WORKSPACE_PATH")
    if raw:
        p = Path(raw).resolve()
        if p.is_dir():
            return p
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def client(workspace_path: Path):
    base_url = os.getenv("EVAL_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=5.0) as http_client:
            yield http_client
        return

    workspace_str = str(workspace_path)
    if workspace_str not in sys.path:
        sys.path.insert(0, workspace_str)

    workspace_env = workspace_path / ".env"
    if workspace_env.is_file():
        os.environ["BENCH_CONFIG_FILE"] = str(workspace_env)

    for mod in list(sys.modules.keys()):
        if mod.startswith("app"):
            sys.modules.pop(mod, None)

    try:
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client
    finally:
        for mod in list(sys.modules.keys()):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)
