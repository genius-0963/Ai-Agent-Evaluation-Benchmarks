import shutil
import tempfile
from pathlib import Path

from agentbench.evaluator import Evaluator
from agentbench.models import RunStatus
from agentbench.scoring import Scorer
from agentbench.task_loader import load_task


def test_evaluator_detects_hardcoded_bypass():
    """If an agent tries to bypass configuration by hardcoding the output, behavior/integrity checks fail."""
    task = load_task("config-recovery-001")
    assert task.task_dir is not None

    with tempfile.TemporaryDirectory() as tmp_dir:
        ws = Path(tmp_dir)
        shutil.copytree(task.task_dir / "app", ws / "app")
        # Agent wrote a hardcoded return value without using settings
        cheating_main = (
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n"
            "@app.get('/health')\ndef health(): return {'status': 'ok'}\n"
            "@app.get('/api/catalog')\ndef catalog(): return {'items': ['alpha', 'beta']}\n"
        )
        (ws / "app/main.py").write_text(cheating_main, encoding="utf-8")
        # And left .env broken
        (ws / ".env").write_text("BENCH_CATALOG_ITEMS=BROKEN", encoding="utf-8")

        evaluator = Evaluator()
        outcome = evaluator.evaluate(task, ws)
        # Should fail configuration and fail anti-hardcoding behavior check
        assert outcome.criteria["configuration"].passed is False
        assert outcome.criteria["behavior"].passed is False
        assert outcome.success is False


def test_status_classification_scenarios():
    """Verify all status classifications from roadmap page 12."""
    pass_thresh = 80.0

    # No changes / fail
    assert Scorer.classify_status(0.0, pass_thresh) == RunStatus.FAILED

    # Correct repair / pass
    assert Scorer.classify_status(100.0, pass_thresh) == RunStatus.PASSED

    # Partial score
    assert Scorer.classify_status(50.0, pass_thresh) == RunStatus.PARTIAL

    # Agent exceeds deadline
    assert (
        Scorer.classify_status(40.0, pass_thresh, timed_out=True) == RunStatus.TIMEOUT
    )

    # Infrastructure error (docker fails)
    assert (
        Scorer.classify_status(0.0, pass_thresh, infrastructure_error=True)
        == RunStatus.INFRASTRUCTURE_ERROR
    )

    # Evaluator crash
    assert (
        Scorer.classify_status(0.0, pass_thresh, evaluator_error=True)
        == RunStatus.EVALUATOR_ERROR
    )
