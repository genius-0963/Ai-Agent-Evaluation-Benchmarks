"""Evaluator Module: test_configuration.py (Weight: 30).

Measures: Expected configuration is valid, parseable, and matches required settings.
"""

import os
import sys
from pathlib import Path


def test_configuration_file_exists(workspace_path: Path):
    """Configuration file must exist in the workspace."""
    env_file = workspace_path / ".env"
    assert env_file.is_file(), f"Expected configuration file missing at {env_file}"


def test_configuration_parses_cleanly(workspace_path: Path):
    """Configuration must parse without ValidationError or SettingsError."""
    workspace_str = str(workspace_path)
    if workspace_str not in sys.path:
        sys.path.insert(0, workspace_str)

    env_file = workspace_path / ".env"
    os.environ["BENCH_CONFIG_FILE"] = str(env_file)
    os.environ.pop("BENCH_CATALOG_ITEMS", None)

    for mod in list(sys.modules.keys()):
        if mod.startswith("app"):
            sys.modules.pop(mod, None)

    try:
        from app.settings import Settings

        settings = Settings()
        assert isinstance(settings.catalog_items, list), "catalog_items must be a list"
        assert len(settings.catalog_items) > 0, "catalog_items must not be empty"
        assert "alpha" in settings.catalog_items, (
            "catalog_items must contain expected items"
        )
    finally:
        for mod in list(sys.modules.keys()):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)
