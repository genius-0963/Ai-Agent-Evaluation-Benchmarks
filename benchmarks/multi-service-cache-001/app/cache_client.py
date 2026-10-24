"""Redis connection pool simulator for multi-service evaluation benchmark."""

from app.config import get_cache_settings


class ConnectionPoolExhaustedError(Exception):
    """Raised when connection pool capacity is exhausted or unavailable."""


class CacheClient:
    def __init__(self) -> None:
        self.settings = get_cache_settings()
        self._in_memory_store: dict[str, str] = {
            "user:42": '{"user_id": 42, "name": "Alice Johnson", "tier": "enterprise"}',
            "user:101": '{"user_id": 101, "name": "Bob Smith", "tier": "standard"}',
        }

    def get(self, key: str) -> str | None:
        cfg = get_cache_settings()
        # Realistic pool check
        if cfg.redis_pool_size <= 0:
            raise ConnectionPoolExhaustedError(
                f"Redis connection pool exhausted: capacity is {cfg.redis_pool_size} (min required: 10)"
            )
        if cfg.redis_port != 6379:
            raise ConnectionPoolExhaustedError(
                f"Connection refused connecting to Redis at {cfg.redis_host}:{cfg.redis_port} (expected 6379)"
            )
        return self._in_memory_store.get(key)


cache_client = CacheClient()
