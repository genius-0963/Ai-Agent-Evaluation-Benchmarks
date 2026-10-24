from pathlib import Path

from agentbench.config import load_framework_config


def test_load_default_framework_config():
    cfg = load_framework_config()
    assert cfg.version == "1.0"
    assert cfg.benchmarks_directory == "benchmarks"
    assert cfg.results_directory == "results"
    assert cfg.docker.default_base_image == "python:3.12-slim"
    assert cfg.docker.auto_cleanup is True


def test_load_custom_config(tmp_path: Path):
    custom_yaml = tmp_path / "custom.yaml"
    custom_yaml.write_text(
        "version: '2.0'\nbenchmarks_directory: 'custom_benchmarks'\n",
        encoding="utf-8",
    )
    cfg = load_framework_config(custom_yaml)
    assert cfg.version == "2.0"
    assert cfg.benchmarks_directory == "custom_benchmarks"
