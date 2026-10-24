from agentbench.matrix import MatrixResult, MatrixRunner
from agentbench.models import BenchmarkReport, RunStatus


def test_matrix_leaderboard_computation():
    mock_report = BenchmarkReport.model_construct(
        schema_version="1.0",
        run_id="r1",
        task_id="t1",
        status=RunStatus.PASSED,
        score=100.0,
        duration_seconds=2.0,
    )

    results = [
        MatrixResult(
            task_id="t1",
            task_name="t1",
            agent_name="agent-a",
            status=RunStatus.PASSED,
            score=100.0,
            duration_seconds=2.0,
            tool_calls=3,
            report=mock_report,
        ),
        MatrixResult(
            task_id="t2",
            task_name="t2",
            agent_name="agent-a",
            status=RunStatus.PASSED,
            score=100.0,
            duration_seconds=2.0,
            tool_calls=3,
            report=mock_report,
        ),
        MatrixResult(
            task_id="t1",
            task_name="t1",
            agent_name="agent-b",
            status=RunStatus.FAILED,
            score=0.0,
            duration_seconds=1.5,
            tool_calls=1,
            report=mock_report,
        ),
    ]

    summaries = MatrixRunner.compute_leaderboard(results)
    assert len(summaries) == 2

    # agent-a is rank 1
    assert summaries[0].agent_name == "agent-a"
    assert summaries[0].success_rate_percent == 100.0
    assert summaries[0].average_score == 100.0
    assert summaries[0].tasks_passed == 2

    # agent-b is rank 2
    assert summaries[1].agent_name == "agent-b"
    assert summaries[1].success_rate_percent == 0.0
    assert summaries[1].average_score == 0.0

    table = MatrixRunner.format_matrix_table(results)
    assert "agent-a" in table
    assert "agent-b" in table

    leaderboard = MatrixRunner.format_leaderboard_table(summaries)
    assert "LEADERBOARD: AGENT CAPABILITY RANKING" in leaderboard
