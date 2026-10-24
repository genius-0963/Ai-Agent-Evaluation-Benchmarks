import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Benchmark Catalog"
    catalog_items: list[str] = ["alpha", "beta"]

    model_config = SettingsConfigDict(
        env_prefix="BENCH_",
        env_file=os.getenv("BENCH_CONFIG_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    """Factory function to load settings dynamically."""
    return Settings()


# Primary singleton instance
settings = get_settings()
