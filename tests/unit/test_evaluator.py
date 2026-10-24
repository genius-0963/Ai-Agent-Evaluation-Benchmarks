import shutil
from pathlib import Path

from agentbench.evaluator import Evaluator
from agentbench.task_loader import load_task


def test_evaluator_verifies_initial_fault(tmp_path: Path):
    task = load_task("config-recovery-001")
    assert task.task_dir is not None

    # Setup a mock broken workspace
    ws = tmp_path / "broken_ws"
    ws.mkdir()
    shutil.copytree(task.task_dir / "app", ws / "app")
    shutil.copyfile(task.task_dir / "fixtures/broken.env", ws / ".env")

    evaluator = Evaluator()
    baseline = evaluator.verify_initial_state(task, ws)
    assert baseline.is_valid is True, "Baseline should confirm fault is present"


def test_evaluator_rejects_healthy_initial_state(tmp_path: Path):
    task = load_task("config-recovery-001")
    assert task.task_dir is not None

    # Setup a mock healthy workspace
    ws = tmp_path / "healthy_ws"
    ws.mkdir()
    shutil.copytree(task.task_dir / "app", ws / "app")
    shutil.copyfile(task.task_dir / "fixtures/repaired.env", ws / ".env")

    evaluator = Evaluator()
    baseline = evaluator.verify_initial_state(task, ws)
    assert baseline.is_valid is False, (
        "Baseline should fail because state is not broken"
    )
