"""Evaluator Module: test_configuration.py (Weight: 25).

Measures: Cache connection pool configuration parameters.
"""

from pathlib import Path


def test_configuration_file_exists(workspace_path: Path):
    env_file = workspace_path / ".env"
    assert env_file.is_file(), f"Configuration file missing: {env_file}"


def test_cache_pool_parameters(workspace_path: Path):
    from app.config import get_cache_settings

    settings = get_cache_settings()
    assert settings.redis_port == 6379, (
        f"Expected redis_port 6379, got {settings.redis_port}"
    )
    assert settings.redis_pool_size >= 10, (
        f"Expected redis_pool_size >= 10, got {settings.redis_pool_size}"
    )
    assert settings.cache_timeout_seconds >= 1.0, "Cache timeout too low"
