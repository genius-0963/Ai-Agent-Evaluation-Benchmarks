"""Framework configuration management."""

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class DockerGlobalConfig(BaseModel):
    default_base_image: str = "python:3.12-slim"
    auto_cleanup: bool = True
    stop_timeout_seconds: int = 5
    enforce_network_isolation: bool = True


class RunnerGlobalConfig(BaseModel):
    default_agent: str = "scripted"
    default_timeout_seconds: int = 180
    capture_logs: bool = True
    save_artifacts: bool = True


class FrameworkConfig(BaseModel):
    version: str = "1.0"
    benchmarks_directory: str = "benchmarks"
    results_directory: str = "results"
    docker: DockerGlobalConfig = Field(default_factory=DockerGlobalConfig)
    runner: RunnerGlobalConfig = Field(default_factory=RunnerGlobalConfig)


def load_framework_config(config_path: str | Path | None = None) -> FrameworkConfig:
    """Load framework configuration from YAML file or default settings."""
    if config_path is None:
        default_candidate = Path("configs/default.yaml")
        if default_candidate.exists():
            config_path = default_candidate

    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f) or {}
            return FrameworkConfig.model_validate(raw_data)

    return FrameworkConfig()
