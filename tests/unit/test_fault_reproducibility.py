import os
import sys

import pytest
from pydantic import ValidationError
from pydantic_settings.exceptions import SettingsError

from agentbench.task_loader import load_task


def test_broken_env_causes_configuration_error():
    """Verify that the broken fixture causes pydantic SettingsError/ValidationError as intended."""
    task = load_task("config-recovery-001")
    assert task.task_dir is not None

    broken_env = task.task_dir / "fixtures/broken.env"
    assert broken_env.exists(), "broken.env fixture must exist"

    # Add task directory to sys.path so 'app.settings' imports
    task_dir_str = str(task.task_dir)
    if task_dir_str not in sys.path:
        sys.path.insert(0, task_dir_str)

    # Clean cached module
    sys.modules.pop("app.settings", None)
    sys.modules.pop("app", None)

    old_env = os.environ.get("BENCH_CONFIG_FILE")
    old_items = os.environ.pop("BENCH_CATALOG_ITEMS", None)
    os.environ["BENCH_CONFIG_FILE"] = str(broken_env)

    try:
        with pytest.raises((ValidationError, SettingsError)) as exc_info:
            from app.settings import get_settings

            get_settings()
        err_msg = str(exc_info.value)
        assert "catalog_items" in err_msg
    finally:
        if old_env is not None:
            os.environ["BENCH_CONFIG_FILE"] = old_env
        else:
            os.environ.pop("BENCH_CONFIG_FILE", None)
        if old_items is not None:
            os.environ["BENCH_CATALOG_ITEMS"] = old_items
        sys.modules.pop("app.settings", None)
        sys.modules.pop("app", None)


def test_repaired_env_restores_health():
    """Verify that the repaired fixture parses correctly into a list."""
    task = load_task("config-recovery-001")
    repaired_env = task.task_dir / "fixtures/repaired.env"
    assert repaired_env.exists(), "repaired.env fixture must exist"

    task_dir_str = str(task.task_dir)
    if task_dir_str not in sys.path:
        sys.path.insert(0, task_dir_str)

    sys.modules.pop("app.settings", None)
    sys.modules.pop("app", None)

    old_env = os.environ.get("BENCH_CONFIG_FILE")
    old_items = os.environ.pop("BENCH_CATALOG_ITEMS", None)
    os.environ["BENCH_CONFIG_FILE"] = str(repaired_env)

    try:
        from app.settings import Settings

        settings = Settings()
        assert settings.catalog_items == ["alpha", "beta"]
    finally:
        if old_env is not None:
            os.environ["BENCH_CONFIG_FILE"] = old_env
        else:
            os.environ.pop("BENCH_CONFIG_FILE", None)
        if old_items is not None:
            os.environ["BENCH_CATALOG_ITEMS"] = old_items
        sys.modules.pop("app.settings", None)
        sys.modules.pop("app", None)


def test_cache_benchmark_broken_env_causes_pool_exhaustion():
    """Verify that broken.env in multi-service-cache-001 triggers pool exhaustion."""
    task = load_task("multi-service-cache-001")
    assert task.task_dir is not None

    broken_env = task.task_dir / "fixtures/broken.env"
    assert broken_env.exists()

    task_dir_str = str(task.task_dir)
    if task_dir_str not in sys.path:
        sys.path.insert(0, task_dir_str)

    sys.modules.pop("app.config", None)
    sys.modules.pop("app.cache_client", None)
    sys.modules.pop("app", None)

    old_env = os.environ.get("BENCH_CONFIG_FILE")
    os.environ["BENCH_CONFIG_FILE"] = str(broken_env)

    try:
        from app.cache_client import CacheClient, ConnectionPoolExhaustedError

        client = CacheClient()
        with pytest.raises(ConnectionPoolExhaustedError):
            client.get("user:42")
    finally:
        if old_env is not None:
            os.environ["BENCH_CONFIG_FILE"] = old_env
        else:
            os.environ.pop("BENCH_CONFIG_FILE", None)
        sys.modules.pop("app.config", None)
        sys.modules.pop("app.cache_client", None)
        sys.modules.pop("app", None)


def test_cache_benchmark_repaired_env_succeeds():
    """Verify that repaired.env in multi-service-cache-001 restores cache retrieval."""
    task = load_task("multi-service-cache-001")
    repaired_env = task.task_dir / "fixtures/repaired.env"
    assert repaired_env.exists()

    task_dir_str = str(task.task_dir)
    if task_dir_str not in sys.path:
        sys.path.insert(0, task_dir_str)

    sys.modules.pop("app.config", None)
    sys.modules.pop("app.cache_client", None)
    sys.modules.pop("app", None)

    old_env = os.environ.get("BENCH_CONFIG_FILE")
    os.environ["BENCH_CONFIG_FILE"] = str(repaired_env)

    try:
        from app.cache_client import CacheClient

        client = CacheClient()
        data = client.get("user:42")
        assert data is not None
        assert "Alice Johnson" in data
    finally:
        if old_env is not None:
            os.environ["BENCH_CONFIG_FILE"] = old_env
        else:
            os.environ.pop("BENCH_CONFIG_FILE", None)
        sys.modules.pop("app.config", None)
        sys.modules.pop("app.cache_client", None)
        sys.modules.pop("app", None)
