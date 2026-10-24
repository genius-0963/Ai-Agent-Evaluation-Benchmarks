"""Task discovery, validation, and loading."""

from pathlib import Path

import yaml

from agentbench.models import BenchmarkTask


class TaskLoadError(Exception):
    """Raised when a benchmark task definition cannot be loaded or is invalid."""


def find_task_directory(
    task_id_or_path: str | Path, benchmarks_dir: Path | str = "benchmarks"
) -> Path:
    """Resolve a task identifier or direct path to its directory."""
    path = Path(task_id_or_path)
    if path.is_dir() and (path / "task.yaml").is_file():
        return path.resolve()

    b_dir = Path(benchmarks_dir)
    if not b_dir.is_dir():
        raise TaskLoadError(f"Benchmarks directory not found: {b_dir.resolve()}")

    # Search by folder name or task.yaml id
    for sub in b_dir.iterdir():
        if sub.is_dir() and (sub / "task.yaml").is_file():
            if sub.name == str(task_id_or_path):
                return sub.resolve()
            try:
                with open(sub / "task.yaml", "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and data.get("id") == str(
                        task_id_or_path
                    ):
                        return sub.resolve()
            except Exception:
                continue

    raise TaskLoadError(
        f"Task '{task_id_or_path}' could not be resolved in {b_dir.resolve()}"
    )


def load_task(
    task_id_or_path: str | Path, benchmarks_dir: Path | str = "benchmarks"
) -> BenchmarkTask:
    """Load a benchmark task from disk and validate its schema."""
    task_dir = find_task_directory(task_id_or_path, benchmarks_dir)
    task_yaml_path = task_dir / "task.yaml"

    try:
        with open(task_yaml_path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except Exception as e:
        raise TaskLoadError(f"Failed to read {task_yaml_path}: {e}") from e

    if not isinstance(raw_data, dict):
        raise TaskLoadError(f"Invalid task.yaml structure in {task_dir}")

    try:
        task = BenchmarkTask.model_validate(raw_data)
    except Exception as e:
        raise TaskLoadError(f"Task validation failed for {task_dir.name}: {e}") from e

    task.task_dir = task_dir

    prompt_path = task_dir / task.agent.prompt_file
    if prompt_path.is_file():
        task.prompt_content = prompt_path.read_text(encoding="utf-8")
    else:
        raise TaskLoadError(
            f"Prompt file '{task.agent.prompt_file}' missing in {task_dir}"
        )

    return task


def list_tasks(benchmarks_dir: Path | str = "benchmarks") -> list[BenchmarkTask]:
    """Discover all valid benchmark tasks in the benchmarks directory."""
    b_dir = Path(benchmarks_dir)
    if not b_dir.is_dir():
        return []

    tasks = []
    for sub in sorted(b_dir.iterdir()):
        if sub.is_dir() and (sub / "task.yaml").is_file():
            try:
                task = load_task(sub, benchmarks_dir)
                tasks.append(task)
            except Exception:
                continue
    return tasks


def validate_task_integrity(task: BenchmarkTask) -> list[str]:
    """Perform comprehensive sanity and file-integrity checks on a task."""
    errors = []
    if not task.task_dir or not task.task_dir.is_dir():
        errors.append("Task directory is not defined or does not exist.")
        return errors

    dockerfile_path = task.task_dir / task.environment.dockerfile
    if not dockerfile_path.is_file():
        errors.append(f"Dockerfile not found: {dockerfile_path}")

    prompt_path = task.task_dir / task.agent.prompt_file
    if not prompt_path.is_file():
        errors.append(f"Prompt file not found: {prompt_path}")

    tests_dir = task.task_dir / task.evaluation.tests_directory
    if not tests_dir.is_dir():
        errors.append(f"Evaluation tests directory not found: {tests_dir}")

    app_dir = task.task_dir / "app"
    if not app_dir.is_dir():
        errors.append(f"Application directory not found: {app_dir}")

    if task.fault.fixture_file:
        fix_path = task.task_dir / task.fault.fixture_file
        if not fix_path.is_file():
            errors.append(f"Fault fixture file not found: {fix_path}")

    return errors
