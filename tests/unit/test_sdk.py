"""Unit tests for the Contributor SDK."""

import tarfile
from pathlib import Path

import pytest

from agentbench.sdk import BenchmarkSDK


def test_sdk_task_scaffolding_and_validation(tmp_path: Path):
    benchmarks_dir = tmp_path / "benchmarks"
    results_dir = tmp_path / "results"
    sdk = BenchmarkSDK(benchmarks_dir=benchmarks_dir, results_dir=results_dir)

    # 1. Create task
    task_dir = sdk.create_task(
        task_id="custom-repair-001",
        name="Custom Microservice Repair",
        category="security",
        difficulty="hard",
    )
    assert task_dir.is_dir()
    assert (task_dir / "task.yaml").is_file()
    assert (task_dir / "prompt.md").is_file()
    assert (task_dir / "fixtures/broken.env").is_file()
    assert (task_dir / "fixtures/repaired.env").is_file()
    assert (task_dir / "app/main.py").is_file()
    assert (task_dir / "tests/test_configuration.py").is_file()
    assert (task_dir / "tests/test_service_health.py").is_file()
    assert (task_dir / "tests/test_behavior.py").is_file()
    assert (task_dir / "tests/test_regression.py").is_file()
    assert (task_dir / "Dockerfile").is_file()

    # Disallow overwrite without flag
    with pytest.raises(FileExistsError):
        sdk.create_task(task_id="custom-repair-001")

    # 2. Validate task
    errors = sdk.validate_task("custom-repair-001")
    assert errors == []


def test_sdk_packaging(tmp_path: Path):
    benchmarks_dir = tmp_path / "benchmarks"
    sdk = BenchmarkSDK(benchmarks_dir=benchmarks_dir)
    sdk.create_task("package-test-001")

    archive_path = tmp_path / "package-test-001.tar.gz"
    pkg = sdk.package_task("package-test-001", output_archive=archive_path)
    assert pkg.is_file()
    assert pkg == archive_path

    with tarfile.open(pkg, "r:gz") as tar:
        names = tar.getnames()
        assert any("task.yaml" in n for n in names)
        assert any("Dockerfile" in n for n in names)


def test_sdk_evaluate_task_programmatic():
    # Evaluate against existing benchmark
    sdk = BenchmarkSDK(benchmarks_dir="benchmarks", results_dir="results")
    summary = sdk.evaluate_task(
        task_id="config-recovery-001",
        agent_name="scripted",
        trials=2,
        k_values=[1, 2],
    )
    assert summary.trials_count == 2
    assert summary.success_count == 2
    assert summary.success_at_1 == 1.0
    assert summary.pass_at_k[1] == 1.0
    assert summary.mean_score == 100.0
