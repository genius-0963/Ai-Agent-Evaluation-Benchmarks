"""Unit tests for statistical evaluation, Pass@k, confidence intervals, and percentiles."""

from datetime import datetime, timezone

import pytest

from agentbench.models import (
    AgentReportInfo,
    BenchmarkReport,
    CriterionDetail,
    FailureClassification,
    RunStatus,
)
from agentbench.stats import (
    calculate_pass_at_k,
    compute_statistical_summary,
    percentile,
)


def test_calculate_pass_at_k_exact_values():
    # 0 trials or k > n
    assert calculate_pass_at_k(0, 0, 1) == 0.0
    assert calculate_pass_at_k(5, 2, 6) == 0.0

    # 0 successes
    assert calculate_pass_at_k(10, 0, 1) == 0.0
    assert calculate_pass_at_k(10, 0, 5) == 0.0

    # All successes
    assert calculate_pass_at_k(5, 5, 1) == 1.0
    assert calculate_pass_at_k(5, 5, 3) == 1.0

    # (n - c) < k => guaranteed at least 1 pass in k
    assert calculate_pass_at_k(5, 4, 2) == 1.0  # 5-4 = 1 < 2

    # Standard formula check: n=10, c=2, k=1 => 2/10 = 0.2
    assert pytest.approx(calculate_pass_at_k(10, 2, 1), rel=1e-3) == 0.2


def test_percentile_calculation():
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile(data, 0.50) == 30.0
    assert percentile(data, 0.0) == 10.0
    assert percentile(data, 1.0) == 50.0
    assert percentile([], 0.5) == 0.0


def _build_dummy_report(
    run_id: str, score: float, passed: bool, duration: float
) -> BenchmarkReport:
    return BenchmarkReport(
        run_id=run_id,
        task_id="test-task-001",
        task_version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        status=RunStatus.PASSED if passed else RunStatus.FAILED,
        failure_classification=FailureClassification.NONE
        if passed
        else FailureClassification.FUNCTIONAL_FAILURE,
        score=score,
        duration_seconds=duration,
        agent=AgentReportInfo(
            name="test-agent",
            tool_calls=3,
            termination_reason="completed",
        ),
        criteria={
            "crit_1": CriterionDetail(weight=50.0, passed=passed, score=score / 2),
            "crit_2": CriterionDetail(weight=50.0, passed=passed, score=score / 2),
        },
        cost_usd=0.01 if passed else 0.005,
        total_tokens=100,
        inference_latency_seconds=1.0,
        execution_latency_seconds=duration - 1.0,
        security_violations=["unauthorized_mount"]
        if not passed and score == 0.0
        else [],
        regression_detected=(not passed and score == 20.0),
    )


def test_compute_statistical_summary():
    reports = [
        _build_dummy_report("r1", 100.0, True, 4.0),
        _build_dummy_report("r2", 100.0, True, 5.0),
        _build_dummy_report("r3", 20.0, False, 3.0),
        _build_dummy_report("r4", 0.0, False, 2.0),
        _build_dummy_report("r5", 100.0, True, 6.0),
    ]

    summary = compute_statistical_summary(reports, k_values=[1, 3])

    assert summary.task_id == "test-task-001"
    assert summary.agent_name == "test-agent"
    assert summary.trials_count == 5
    assert summary.success_count == 3
    assert summary.success_at_1 == 0.6  # 3/5
    assert 1 in summary.pass_at_k
    assert 3 in summary.pass_at_k
    assert summary.pass_at_k[1] == pytest.approx(0.6, rel=1e-2)
    assert summary.mean_score == pytest.approx(64.0, rel=1e-2)
    assert summary.score_variance > 0
    assert summary.median_latency_seconds == 4.0
    assert summary.violation_rate == 0.2  # 1 out of 5 has violation
    assert summary.regression_rate == 0.2  # 1 out of 5 has regression


def test_empty_reports_raises_error():
    with pytest.raises(
        ValueError, match="Cannot compute statistics on empty report list"
    ):
        compute_statistical_summary([])
