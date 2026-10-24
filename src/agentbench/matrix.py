"""Comparative matrix execution and leaderboard reporting across multiple agents and benchmarks."""

import time
from dataclasses import dataclass
from pathlib import Path

from agentbench.models import BenchmarkReport, RunStatus
from agentbench.runner import BenchmarkRunner
from agentbench.task_loader import list_tasks


@dataclass
class MatrixResult:
    """Aggregated outcome of running an agent against a benchmark task."""

    task_id: str
    task_name: str
    agent_name: str
    status: RunStatus
    score: float
    duration_seconds: float
    tool_calls: int
    report: BenchmarkReport


@dataclass
class AgentLeaderboardSummary:
    """Summary metrics for a specific agent across all tasks in the matrix."""

    agent_name: str
    tasks_run: int = 0
    tasks_passed: int = 0
    average_score: float = 0.0
    total_duration_seconds: float = 0.0
    total_tool_calls: int = 0
    success_rate_percent: float = 0.0


class MatrixRunner:
    """Runs a combinatorial matrix of benchmark tasks against candidate agents."""

    def __init__(
        self,
        benchmarks_dir: str | Path = "benchmarks",
        results_dir: str | Path = "results",
        use_docker: bool = False,
    ) -> None:
        self.runner = BenchmarkRunner(
            benchmarks_dir=benchmarks_dir,
            results_dir=results_dir,
            use_docker=use_docker,
        )
        self.benchmarks_dir = benchmarks_dir

    def run_matrix(
        self,
        task_ids: list[str] | None = None,
        agent_names: list[str] | None = None,
    ) -> list[MatrixResult]:
        """Execute all combinations of requested tasks and agents."""
        if not task_ids or "all" in task_ids:
            all_tasks = list_tasks(self.benchmarks_dir)
            task_ids = [t.id for t in all_tasks]

        if not agent_names:
            agent_names = ["scripted", "noop", "llm"]

        results: list[MatrixResult] = []

        for tid in task_ids:
            for ag in agent_names:
                run_id = f"matrix-{tid[:12]}-{ag}-{int(time.time())}"
                report = self.runner.run(task_id=tid, agent_name=ag, run_id=run_id)
                results.append(
                    MatrixResult(
                        task_id=tid,
                        task_name=report.task_id,
                        agent_name=ag,
                        status=report.status,
                        score=report.score,
                        duration_seconds=report.duration_seconds,
                        tool_calls=report.agent.tool_calls,
                        report=report,
                    )
                )

        return results

    @staticmethod
    def compute_leaderboard(
        results: list[MatrixResult],
    ) -> list[AgentLeaderboardSummary]:
        """Aggregate run results into per-agent performance summaries."""
        by_agent: dict[str, list[MatrixResult]] = {}
        for r in results:
            by_agent.setdefault(r.agent_name, []).append(r)

        summaries = []
        for ag, runs in by_agent.items():
            total = len(runs)
            passed = sum(1 for r in runs if r.status == RunStatus.PASSED)
            avg_score = sum(r.score for r in runs) / total if total > 0 else 0.0
            total_duration = sum(r.duration_seconds for r in runs)
            total_tools = sum(r.tool_calls for r in runs)

            summaries.append(
                AgentLeaderboardSummary(
                    agent_name=ag,
                    tasks_run=total,
                    tasks_passed=passed,
                    average_score=round(avg_score, 1),
                    total_duration_seconds=round(total_duration, 2),
                    total_tool_calls=total_tools,
                    success_rate_percent=round((passed / total) * 100.0, 1)
                    if total > 0
                    else 0.0,
                )
            )

        # Sort by Success Rate (desc), then Average Score (desc)
        summaries.sort(
            key=lambda s: (s.success_rate_percent, s.average_score), reverse=True
        )
        return summaries

    @staticmethod
    def format_matrix_table(results: list[MatrixResult]) -> str:
        """Render a formatted ASCII table of matrix outcomes."""
        lines = [
            "=" * 85,
            f"{'TASK ID':<24} {'AGENT':<18} {'STATUS':<10} {'SCORE':<8} {'TOOLS':<8} {'DURATION':<10}",
            "-" * 85,
        ]
        for r in results:
            icon = "✓" if r.status == RunStatus.PASSED else "✗"
            st = f"{r.status.value.upper()} [{icon}]"
            lines.append(
                f"{r.task_id:<24} {r.agent_name:<18} {st:<10} {r.score:<8.1f} {r.tool_calls:<8} {r.duration_seconds:<10.2f}s"
            )
        lines.append("=" * 85)
        return "\n".join(lines)

    @staticmethod
    def format_leaderboard_table(summaries: list[AgentLeaderboardSummary]) -> str:
        """Render leaderboard ranking table."""
        lines = [
            "=" * 85,
            "LEADERBOARD: AGENT CAPABILITY RANKING",
            "=" * 85,
            f"{'RANK':<6} {'AGENT NAME':<22} {'SUCCESS@1':<12} {'AVG SCORE':<12} {'PASSED':<10} {'TOTAL TIME':<12}",
            "-" * 85,
        ]
        for rank, s in enumerate(summaries, start=1):
            succ = f"{s.success_rate_percent:.1f}%"
            score = f"{s.average_score:.1f} / 100"
            pass_str = f"{s.tasks_passed}/{s.tasks_run}"
            dur = f"{s.total_duration_seconds:.2f}s"
            lines.append(
                f"{rank:<6} {s.agent_name:<22} {succ:<12} {score:<12} {pass_str:<10} {dur:<12}"
            )
        lines.append("=" * 85)
        return "\n".join(lines)
