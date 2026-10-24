from agentbench.models import RunStatus
from agentbench.scoring import Scorer


def test_scorer_all_pass():
    results = {
        "configuration": True,
        "startup": True,
        "behavior": True,
        "regression": True,
    }
    score = Scorer.calculate_score(results)
    assert score == 100.0


def test_scorer_partial_pass():
    results = {
        "configuration": True,
        "startup": True,
        "behavior": False,
        "regression": False,
    }
    score = Scorer.calculate_score(results)
    assert score == 50.0  # 30 + 20


def test_status_classification():
    assert Scorer.classify_status(100.0, 80.0) == RunStatus.PASSED
    assert Scorer.classify_status(50.0, 80.0) == RunStatus.PARTIAL
    assert Scorer.classify_status(0.0, 80.0) == RunStatus.FAILED
    assert Scorer.classify_status(100.0, 80.0, timed_out=True) == RunStatus.TIMEOUT
    assert (
        Scorer.classify_status(100.0, 80.0, infrastructure_error=True)
        == RunStatus.INFRASTRUCTURE_ERROR
    )
    assert (
        Scorer.classify_status(100.0, 80.0, evaluator_error=True)
        == RunStatus.EVALUATOR_ERROR
    )
