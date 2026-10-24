import pytest
from pydantic import ValidationError

from agentbench.models import (
    AgentReportInfo,
    BenchmarkReport,
    BenchmarkTask,
    CriterionDetail,
    FaultConfig,
    RunStatus,
    ScoringCriteria,
)


def test_scoring_criteria_weights_must_sum_to_100():
    valid = ScoringCriteria(configuration=30, startup=20, behavior=30, regression=20)
    assert valid.configuration == 30

    with pytest.raises(ValidationError) as exc:
        ScoringCriteria(configuration=10, startup=10, behavior=10, regression=10)
    assert "Scoring weights must sum to 100" in str(exc.value)


def test_benchmark_task_instantiation():
    task = BenchmarkTask(
        id="sample-001",
        name="Sample Task",
        description="A sample test task",
        fault=FaultConfig(type="invalid_config"),
    )
    assert task.id == "sample-001"
    assert task.environment.startup_timeout_seconds == 30
    assert task.agent.max_tool_calls == 40


def test_benchmark_report_validation():
    report = BenchmarkReport(
        schema_version="1.0",
        run_id="test-run-123",
        task_id="config-recovery-001",
        status=RunStatus.PASSED,
        score=100.0,
        duration_seconds=12.5,
        agent=AgentReportInfo(
            name="test-agent", tool_calls=2, termination_reason="completed"
        ),
        criteria={
            "configuration": CriterionDetail(weight=30, passed=True, score=30),
        },
    )
    assert report.score == 100.0
    assert report.status == RunStatus.PASSED
