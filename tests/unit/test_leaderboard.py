"""Unit tests for experiment tracking, leaderboard aggregation, and export."""

from datetime import datetime, timezone
from pathlib import Path

from agentbench.leaderboard import (
    ExperimentTracker,
    LeaderboardAggregator,
    generate_html_leaderboard,
    generate_markdown_leaderboard,
)
from agentbench.models import (
    AgentReportInfo,
    BenchmarkReport,
    CriterionDetail,
    FailureClassification,
    RunStatus,
)


def _sample_report(
    run_id: str, agent: str, task: str, score: float, passed: bool
) -> BenchmarkReport:
    return BenchmarkReport(
        run_id=run_id,
        task_id=task,
        task_version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        status=RunStatus.PASSED if passed else RunStatus.FAILED,
        failure_classification=FailureClassification.NONE
        if passed
        else FailureClassification.FUNCTIONAL_FAILURE,
        score=score,
        duration_seconds=3.5,
        agent=AgentReportInfo(
            name=agent,
            tool_calls=4,
            termination_reason="completed",
            model_version="gpt-4o",
        ),
        criteria={
            "c1": CriterionDetail(weight=50.0, passed=passed, score=score / 2),
            "c2": CriterionDetail(weight=50.0, passed=passed, score=score / 2),
        },
        cost_usd=0.02,
        total_tokens=450,
        security_violations=[],
        regression_detected=False,
    )


def test_experiment_tracker_lifecycle(tmp_path: Path):
    index_file = tmp_path / "experiments_index.json"
    tracker = ExperimentTracker(index_file)

    assert tracker.load_all() == []

    rep1 = _sample_report("run-1", "agent-a", "task-1", 100.0, True)
    tracker.record(rep1)

    loaded = tracker.load_all()
    assert len(loaded) == 1
    assert loaded[0]["run_id"] == "run-1"
    assert loaded[0]["passed"] is True
    assert loaded[0]["agent_name"] == "agent-a"

    # Update existing run
    rep1_updated = _sample_report("run-1", "agent-a", "task-1", 80.0, True)
    tracker.record(rep1_updated)
    loaded = tracker.load_all()
    assert len(loaded) == 1
    assert loaded[0]["score"] == 80.0

    tracker.clear()
    assert tracker.load_all() == []


def test_leaderboard_aggregator_metrics():
    experiments = [
        {
            "run_id": "r1",
            "agent_name": "agent-a",
            "task_id": "t1",
            "passed": True,
            "score": 100.0,
            "duration_seconds": 2.0,
            "cost_usd": 0.01,
            "total_tokens": 100,
            "tool_calls": 2,
            "violation_count": 0,
            "regression_detected": False,
            "model_name": "mock",
        },
        {
            "run_id": "r2",
            "agent_name": "agent-a",
            "task_id": "t1",
            "passed": True,
            "score": 100.0,
            "duration_seconds": 2.5,
            "cost_usd": 0.01,
            "total_tokens": 100,
            "tool_calls": 2,
            "violation_count": 0,
            "regression_detected": False,
            "model_name": "mock",
        },
        {
            "run_id": "r3",
            "agent_name": "agent-a",
            "task_id": "t1",
            "passed": False,
            "score": 40.0,
            "duration_seconds": 3.0,
            "cost_usd": 0.01,
            "total_tokens": 100,
            "tool_calls": 2,
            "violation_count": 0,
            "regression_detected": False,
            "model_name": "mock",
        },
        {
            "run_id": "r4",
            "agent_name": "agent-b",
            "task_id": "t1",
            "passed": False,
            "score": 0.0,
            "duration_seconds": 1.0,
            "cost_usd": 0.00,
            "total_tokens": 0,
            "tool_calls": 0,
            "violation_count": 1,
            "regression_detected": True,
            "model_name": "mock",
        },
    ]

    agent_summaries = LeaderboardAggregator.aggregate_agents(experiments)
    assert len(agent_summaries) == 2

    # Top agent should be agent-a
    top = agent_summaries[0]
    assert top["agent_name"] == "agent-a"
    assert top["runs_count"] == 3
    assert top["passed_count"] == 2
    assert top["success_rate_percent"] == 66.7
    assert top["mean_score"] == 80.0

    bottom = agent_summaries[1]
    assert bottom["agent_name"] == "agent-b"
    assert bottom["success_rate_percent"] == 0.0
    assert bottom["violation_rate_percent"] == 100.0
    assert bottom["regression_rate_percent"] == 100.0

    task_summaries = LeaderboardAggregator.aggregate_tasks(experiments)
    assert len(task_summaries) == 1
    assert task_summaries[0]["task_id"] == "t1"
    assert task_summaries[0]["total_runs"] == 4
    assert task_summaries[0]["passed_runs"] == 2


def test_generate_html_and_markdown(tmp_path: Path):
    experiments = [
        {
            "run_id": "r1",
            "agent_name": "agent-a",
            "task_id": "t1",
            "passed": True,
            "score": 100.0,
            "duration_seconds": 2.0,
            "cost_usd": 0.01,
            "total_tokens": 100,
            "tool_calls": 2,
            "violation_count": 0,
            "regression_detected": False,
            "model_name": "mock",
            "timestamp": "2026-10-24T12:00:00Z",
        },
    ]

    html_file = tmp_path / "leaderboard.html"
    md_file = tmp_path / "LEADERBOARD.md"

    out_html = generate_html_leaderboard(experiments, output_path=html_file)
    assert out_html.is_file()
    html_text = out_html.read_text()
    assert "<!DOCTYPE html>" in html_text
    assert "agent-a" in html_text
    assert "Agent Capability Leaderboard" in html_text

    out_md = generate_markdown_leaderboard(experiments, output_path=md_file)
    assert md_file.is_file()
    assert "Official Leaderboard" in out_md
    assert "agent-a" in out_md
