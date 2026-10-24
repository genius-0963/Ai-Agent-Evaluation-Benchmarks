"""Evaluator Module: test_behavior.py (Weight: 30).

Measures: Catalog returns configured items and dynamic configuration is preserved.
Includes dynamic canary injection to reject hardcoded cheating.
"""

import json
import os
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


def test_catalog_returns_expected_items(client):
    """GET /api/catalog must return configured items."""
    response = client.get("/api/catalog")
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "items" in body, "Response body must contain 'items' key"
    assert body["items"] == ["alpha", "beta"], (
        f"Expected items ['alpha', 'beta'], got {body['items']}"
    )


def test_catalog_is_backed_by_settings(workspace_path: Path):
    """Ensure the catalog endpoint logic does not hardcode items and uses settings."""
    main_file = workspace_path / "app/main.py"
    if main_file.is_file():
        content = main_file.read_text(encoding="utf-8")
        # Anti-hardcoding check: main.py must reference settings.catalog_items
        assert "settings.catalog_items" in content, (
            "Integrity check failed: get_catalog() must reference settings.catalog_items, "
            "not a hardcoded list."
        )


def test_catalog_dynamic_canary_mutation(workspace_path: Path):
    """Anti-Cheating: Inject randomized canary items into configuration and verify dynamic reflection."""
    workspace_str = str(workspace_path)
    if workspace_str not in sys.path:
        sys.path.insert(0, workspace_str)

    canary_token_1 = f"canary-{uuid.uuid4().hex[:6]}"
    canary_token_2 = f"canary-{uuid.uuid4().hex[:6]}"
    canary_list = [canary_token_1, canary_token_2]

    env_file = workspace_path / ".env"
    assert env_file.is_file(), "Workspace must have .env file"
    original_env_content = env_file.read_text(encoding="utf-8")

    try:
        # Mutate config with canary items
        canary_content = (
            'BENCH_APP_NAME="Benchmark Catalog"\n'
            f"BENCH_CATALOG_ITEMS={json.dumps(canary_list)}\n"
        )
        env_file.write_text(canary_content, encoding="utf-8")

        # Clean module cache
        for mod in list(sys.modules.keys()):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)

        os.environ["BENCH_CONFIG_FILE"] = str(env_file)
        os.environ.pop("BENCH_CATALOG_ITEMS", None)

        from app.main import app

        with TestClient(app) as test_client:
            resp = test_client.get("/api/catalog")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("items") == canary_list, (
                "Anti-cheating verification failed: Endpoint returned static/hardcoded response "
                "instead of dynamically reflecting configuration changes."
            )
    finally:
        # Restore original repaired config
        env_file.write_text(original_env_content, encoding="utf-8")
        for mod in list(sys.modules.keys()):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)
