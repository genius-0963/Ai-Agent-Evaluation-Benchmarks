"""Evaluator Module: test_configuration.py (Weight: 20).

Measures: Application code is syntactically valid and app object is properly defined.
"""

from pathlib import Path


def test_app_main_exists(workspace_path: Path):
    main_file = workspace_path / "app/main.py"
    assert main_file.is_file(), f"File missing: {main_file}"


def test_app_imports_cleanly(client):
    assert client is not None
