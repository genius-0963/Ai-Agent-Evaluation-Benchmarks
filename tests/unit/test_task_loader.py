import pytest

from agentbench.task_loader import (
    TaskLoadError,
    list_tasks,
    load_task,
    validate_task_integrity,
)


def test_load_task_success():
    task = load_task("config-recovery-001")
    assert task.id == "config-recovery-001"
    assert task.version == "1.0.0"
    assert task.environment.memory_limit == "512m"
    assert task.prompt_content != ""
    assert "Restore the Catalog Service" in task.prompt_content


def test_list_tasks_discovers_config_recovery():
    tasks = list_tasks("benchmarks")
    ids = [t.id for t in tasks]
    assert "config-recovery-001" in ids
    assert "contract-repair-001" in ids
    assert "multi-service-cache-001" in ids


def test_validate_task_integrity():
    for task_id in [
        "config-recovery-001",
        "contract-repair-001",
        "multi-service-cache-001",
    ]:
        task = load_task(task_id)
        errors = validate_task_integrity(task)
        assert errors == [], f"Validation errors for {task_id}: {errors}"


def test_load_nonexistent_task_raises_error():
    with pytest.raises(TaskLoadError):
        load_task("nonexistent-task-999")
