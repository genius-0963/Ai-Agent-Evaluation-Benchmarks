import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class CacheSettings(BaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_pool_size: int = 20
    cache_timeout_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=os.getenv("BENCH_CONFIG_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_cache_settings() -> CacheSettings:
    return CacheSettings()


settings = get_cache_settings()
