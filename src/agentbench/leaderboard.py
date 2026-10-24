"""Public leaderboard generator, experiment history tracking, and HTML/Markdown dashboard export."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentbench.models import BenchmarkReport, RunStatus
from agentbench.stats import calculate_pass_at_k, percentile

logger = logging.getLogger("agentbench.leaderboard")

DEFAULT_INDEX_PATH = Path("results/experiments_index.json")
DEFAULT_HTML_PATH = Path("results/leaderboard.html")
DEFAULT_MD_PATH = Path("results/LEADERBOARD.md")


class ExperimentTracker:
    """Manages persistent experiment run history and auditable execution logs."""

    def __init__(self, index_path: str | Path = DEFAULT_INDEX_PATH) -> None:
        self.index_path = Path(index_path)

    def record(self, report: BenchmarkReport) -> dict[str, Any]:
        """Record a benchmark execution report into the persistent index."""
        ts = getattr(report, "timestamp", None)
        if isinstance(ts, datetime):
            ts_str = ts.isoformat()
        elif ts:
            ts_str = str(ts)
        else:
            ts_str = datetime.now(timezone.utc).isoformat()

        model_str = getattr(report.agent, "model_version", None) or getattr(
            report.agent, "model", "default"
        )

        record: dict[str, Any] = {
            "run_id": report.run_id,
            "timestamp": ts_str,
            "task_id": report.task_id,
            "task_version": report.task_version,
            "agent_name": report.agent.name,
            "model_name": model_str,
            "status": report.status.value,
            "score": report.score,
            "passed": report.status == RunStatus.PASSED,
            "duration_seconds": report.duration_seconds,
            "execution_latency_seconds": report.execution_latency_seconds,
            "inference_latency_seconds": report.inference_latency_seconds,
            "tool_calls": report.agent.tool_calls,
            "total_tokens": report.total_tokens,
            "cost_usd": report.cost_usd,
            "security_violations": report.security_violations,
            "violation_count": len(report.security_violations),
            "regression_detected": report.regression_detected,
            "failure_type": report.failure_classification.value
            if hasattr(report.failure_classification, "value")
            else str(report.failure_classification or "NONE"),
            "artifacts": [str(a) for a in report.artifacts],
        }

        experiments = self.load_all()
        # Update if run_id already exists, otherwise append
        existing_idx = next(
            (
                i
                for i, exp in enumerate(experiments)
                if exp.get("run_id") == report.run_id
            ),
            None,
        )
        if existing_idx is not None:
            experiments[existing_idx] = record
        else:
            experiments.append(record)

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(experiments, indent=2), encoding="utf-8")
        return record

    def load_all(self) -> list[dict[str, Any]]:
        """Load all recorded experiments from index file."""
        if not self.index_path.is_file():
            return []
        try:
            content = self.index_path.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as e:
            logger.warning(
                "Failed to parse experiment index from %s: %s", self.index_path, e
            )
            return []

    def clear(self) -> None:
        """Clear all experiment history."""
        if self.index_path.is_file():
            self.index_path.unlink()


class LeaderboardAggregator:
    """Aggregates experiment records into agent-level and task-level metrics."""

    @staticmethod
    def aggregate_agents(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group experiments by agent and compute statistical performance metrics."""
        by_agent: dict[str, list[dict[str, Any]]] = {}
        for exp in experiments:
            agent_key = exp.get("agent_name", "unknown")
            by_agent.setdefault(agent_key, []).append(exp)

        aggregated: list[dict[str, Any]] = []

        for agent_key, runs in by_agent.items():
            total = len(runs)
            if total == 0:
                continue

            passed = sum(1 for r in runs if r.get("passed", False))
            success_rate = round((passed / total) * 100.0, 1)

            scores = [float(r.get("score", 0.0)) for r in runs]
            mean_score = round(sum(scores) / total, 1)

            durations = [float(r.get("duration_seconds", 0.0)) for r in runs]
            p50_lat = round(percentile(durations, 0.50), 2)
            p95_lat = round(percentile(durations, 0.95), 2)

            total_cost = sum(float(r.get("cost_usd", 0.0)) for r in runs)
            cost_per_pass = round(total_cost / passed, 4) if passed > 0 else 0.0

            total_tokens = sum(int(r.get("total_tokens", 0)) for r in runs)
            mean_tools = round(
                sum(int(r.get("tool_calls", 0)) for r in runs) / total, 1
            )

            violations = sum(1 for r in runs if r.get("violation_count", 0) > 0)
            violation_rate = round((violations / total) * 100.0, 1)

            regressions = sum(1 for r in runs if r.get("regression_detected", False))
            regression_rate = round((regressions / total) * 100.0, 1)

            # Pass@k estimation if multiple runs per task exist
            task_groups: dict[str, list[dict[str, Any]]] = {}
            for r in runs:
                task_groups.setdefault(r.get("task_id", ""), []).append(r)

            pass_at_3_estimates: list[float] = []
            for tid, t_runs in task_groups.items():
                if len(t_runs) >= 3:
                    c = sum(1 for tr in t_runs if tr.get("passed", False))
                    pass_at_3_estimates.append(calculate_pass_at_k(len(t_runs), c, 3))

            pass_at_3 = (
                round((sum(pass_at_3_estimates) / len(pass_at_3_estimates)) * 100.0, 1)
                if pass_at_3_estimates
                else None
            )

            model_name = runs[0].get("model_name", "N/A")

            aggregated.append(
                {
                    "agent_name": agent_key,
                    "model_name": model_name,
                    "runs_count": total,
                    "passed_count": passed,
                    "success_rate_percent": success_rate,
                    "pass_at_3_percent": pass_at_3,
                    "mean_score": mean_score,
                    "p50_latency_seconds": p50_lat,
                    "p95_latency_seconds": p95_lat,
                    "total_cost_usd": round(total_cost, 4),
                    "cost_per_pass_usd": cost_per_pass,
                    "mean_tool_calls": mean_tools,
                    "total_tokens": total_tokens,
                    "violation_rate_percent": violation_rate,
                    "regression_rate_percent": regression_rate,
                }
            )

        # Sort by Success Rate descending, then Mean Score descending, then Cost ascending
        aggregated.sort(
            key=lambda a: (
                a["success_rate_percent"],
                a["mean_score"],
                -a["cost_per_pass_usd"],
            ),
            reverse=True,
        )
        return aggregated

    @staticmethod
    def aggregate_tasks(experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group experiments by task to measure benchmark difficulty and failure rates."""
        by_task: dict[str, list[dict[str, Any]]] = {}
        for exp in experiments:
            tid = exp.get("task_id", "unknown")
            by_task.setdefault(tid, []).append(exp)

        aggregated: list[dict[str, Any]] = []
        for tid, runs in by_task.items():
            total = len(runs)
            passed = sum(1 for r in runs if r.get("passed", False))
            success_rate = round((passed / total) * 100.0, 1) if total > 0 else 0.0
            avg_score = (
                round(sum(float(r.get("score", 0.0)) for r in runs) / total, 1)
                if total > 0
                else 0.0
            )
            avg_duration = (
                round(
                    sum(float(r.get("duration_seconds", 0.0)) for r in runs) / total, 2
                )
                if total > 0
                else 0.0
            )

            aggregated.append(
                {
                    "task_id": tid,
                    "total_runs": total,
                    "passed_runs": passed,
                    "success_rate_percent": success_rate,
                    "average_score": avg_score,
                    "average_duration_seconds": avg_duration,
                }
            )

        aggregated.sort(key=lambda t: t["success_rate_percent"])
        return aggregated


def generate_markdown_leaderboard(
    experiments: list[dict[str, Any]],
    output_path: str | Path | None = DEFAULT_MD_PATH,
) -> str:
    """Generate GitHub-flavored Markdown leaderboard and optionally write to file."""
    agent_summaries = LeaderboardAggregator.aggregate_agents(experiments)
    task_summaries = LeaderboardAggregator.aggregate_tasks(experiments)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# AI Agent Evaluation Benchmarks — Official Leaderboard",
        "",
        f"> **Last Updated**: {now_str} | **Total Benchmark Trials**: {len(experiments)}",
        "",
        "## Agent Capability Rankings",
        "",
        "| Rank | Agent | Model | Success@1 | Pass@3 | Mean Score | Cost/Pass | Latency (p50/p95) | Violations |",
        "| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for rank, ag in enumerate(agent_summaries, start=1):
        p3_str = (
            f"{ag['pass_at_3_percent']}%"
            if ag["pass_at_3_percent"] is not None
            else "—"
        )
        cost_str = (
            f"${ag['cost_per_pass_usd']:.4f}"
            if ag["cost_per_pass_usd"] > 0
            else "$0.00"
        )
        lat_str = f"{ag['p50_latency_seconds']}s / {ag['p95_latency_seconds']}s"
        lines.append(
            f"| **{rank}** | `{ag['agent_name']}` | `{ag['model_name']}` | "
            f"**{ag['success_rate_percent']}%** | {p3_str} | {ag['mean_score']}/100 | "
            f"{cost_str} | {lat_str} | {ag['violation_rate_percent']}% |"
        )

    lines.extend(
        [
            "",
            "## Task Diagnostic Overview",
            "",
            "| Task ID | Total Attempts | Passed | Solve Rate | Avg Score | Avg Duration |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    for ts in task_summaries:
        lines.append(
            f"| `{ts['task_id']}` | {ts['total_runs']} | {ts['passed_runs']} | "
            f"**{ts['success_rate_percent']}%** | {ts['average_score']} | {ts['average_duration_seconds']}s |"
        )

    content = "\n".join(lines) + "\n"

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    return content


def generate_html_leaderboard(
    experiments: list[dict[str, Any]],
    output_path: str | Path = DEFAULT_HTML_PATH,
    title: str = "AgentBench Leaderboard & Evaluation History",
) -> Path:
    """Generate modern, zero-dependency, interactive HTML dashboard."""
    agent_summaries = LeaderboardAggregator.aggregate_agents(experiments)
    task_summaries = LeaderboardAggregator.aggregate_tasks(experiments)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    total_runs = len(experiments)
    total_passed = sum(1 for e in experiments if e.get("passed", False))
    overall_solve_rate = (
        round((total_passed / total_runs) * 100.0, 1) if total_runs > 0 else 0.0
    )
    top_agent = agent_summaries[0]["agent_name"] if agent_summaries else "None"

    # Recent runs table (last 50 runs descending)
    recent_runs = list(reversed(experiments))[:50]

    agent_rows_html = []
    for rank, ag in enumerate(agent_summaries, start=1):
        badge_class = (
            "badge-gold"
            if rank == 1
            else "badge-silver"
            if rank == 2
            else "badge-bronze"
            if rank == 3
            else "badge-neutral"
        )
        p3_str = (
            f"{ag['pass_at_3_percent']}%"
            if ag["pass_at_3_percent"] is not None
            else "&mdash;"
        )
        cost_str = (
            f"${ag['cost_per_pass_usd']:.4f}"
            if ag["cost_per_pass_usd"] > 0
            else "$0.00"
        )
        agent_rows_html.append(
            f"""
            <tr>
                <td class="text-center"><span class="badge {badge_class}">#{rank}</span></td>
                <td><strong>{ag["agent_name"]}</strong></td>
                <td><code>{ag["model_name"]}</code></td>
                <td class="text-right"><strong>{ag["success_rate_percent"]}%</strong></td>
                <td class="text-right">{p3_str}</td>
                <td class="text-right">{ag["mean_score"]} / 100</td>
                <td class="text-right">{ag["runs_count"]}</td>
                <td class="text-right">{cost_str}</td>
                <td class="text-right">{ag["p50_latency_seconds"]}s / {ag["p95_latency_seconds"]}s</td>
                <td class="text-right">{ag["violation_rate_percent"]}%</td>
            </tr>
            """
        )

    task_rows_html = []
    for ts in task_summaries:
        task_rows_html.append(
            f"""
            <tr>
                <td><code>{ts["task_id"]}</code></td>
                <td class="text-right">{ts["total_runs"]}</td>
                <td class="text-right">{ts["passed_runs"]}</td>
                <td class="text-right"><strong>{ts["success_rate_percent"]}%</strong></td>
                <td class="text-right">{ts["average_score"]}</td>
                <td class="text-right">{ts["average_duration_seconds"]}s</td>
            </tr>
            """
        )

    run_rows_html = []
    for r in recent_runs:
        st = r.get("status", "UNKNOWN").upper()
        badge_type = (
            "status-pass"
            if st == "PASSED"
            else "status-fail"
            if st in ["FAILED", "PARTIAL"]
            else "status-warn"
        )
        sec_viol = len(r.get("security_violations", []))
        viol_badge = (
            f'<span class="badge badge-danger">{sec_viol} viol</span>'
            if sec_viol > 0
            else '<span class="text-muted">None</span>'
        )
        run_rows_html.append(
            f"""
            <tr class="run-row" data-agent="{r.get("agent_name", "")}" data-task="{r.get("task_id", "")}">
                <td><code>{r.get("run_id", "")}</code></td>
                <td><code>{r.get("task_id", "")}</code></td>
                <td>{r.get("agent_name", "")}</td>
                <td><span class="badge {badge_type}">{st}</span></td>
                <td class="text-right">{r.get("score", 0.0)}</td>
                <td class="text-right">{r.get("duration_seconds", 0.0):.2f}s</td>
                <td>{viol_badge}</td>
                <td class="text-muted">{r.get("timestamp", "")[:19]}</td>
            </tr>
            """
        )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg: #090d16;
            --surface: #131c2e;
            --surface-hover: #1a273f;
            --border: #22324e;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            padding: 32px 24px;
            line-height: 1.5;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ margin-bottom: 32px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
        h1 {{ font-size: 26px; font-weight: 700; color: #fff; margin-bottom: 6px; }}
        p.subtitle {{ color: var(--text-muted); font-size: 14px; }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }}
        .card .title {{ font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; }}
        .card .value {{ font-size: 28px; font-weight: 700; color: #fff; }}
        .card .sub {{ font-size: 12px; color: var(--accent); margin-top: 4px; }}

        section {{ margin-bottom: 40px; }}
        h2 {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
            font-size: 14px;
        }}
        th, td {{ padding: 12px 16px; border-bottom: 1px solid var(--border); }}
        th {{ background: #0c1424; color: var(--text-muted); font-weight: 600; text-align: left; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
        tr:hover td {{ background: var(--surface-hover); }}
        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}
        .text-muted {{ color: var(--text-muted); font-size: 12px; }}

        code {{
            background: #1e293b;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            color: #7dd3fc;
        }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-gold {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }}
        .badge-silver {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.4); }}
        .badge-bronze {{ background: rgba(180, 83, 9, 0.2); color: #f59e0b; border: 1px solid rgba(180, 83, 9, 0.4); }}
        .badge-neutral {{ background: rgba(255, 255, 255, 0.05); color: #94a3b8; }}

        .status-pass {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}
        .status-fail {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .status-warn {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }}
        .badge-danger {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}

        .search-box {{
            width: 100%;
            max-width: 360px;
            padding: 8px 14px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 6px;
            color: #fff;
            margin-bottom: 16px;
            outline: none;
        }}
        .search-box:focus {{ border-color: var(--accent); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <p class="subtitle">Auditable evaluation benchmark for software engineering and autonomous agents &bull; Updated: {now_str}</p>
        </header>

        <div class="metrics-grid">
            <div class="card">
                <div class="title">Total Evaluations</div>
                <div class="value">{total_runs}</div>
                <div class="sub">Across all registered agents</div>
            </div>
            <div class="card">
                <div class="title">Overall Solve Rate</div>
                <div class="value">{overall_solve_rate}%</div>
                <div class="sub">{total_passed} passed trials</div>
            </div>
            <div class="card">
                <div class="title">Top Ranking Agent</div>
                <div class="value">{top_agent}</div>
                <div class="sub">By Success@1 &amp; score</div>
            </div>
            <div class="card">
                <div class="title">Active Benchmarks</div>
                <div class="value">{len(task_summaries)}</div>
                <div class="sub">Deterministic suites</div>
            </div>
        </div>

        <section>
            <h2>Agent Capability Leaderboard</h2>
            <table>
                <thead>
                    <tr>
                        <th class="text-center">Rank</th>
                        <th>Agent</th>
                        <th>Model Adapter</th>
                        <th class="text-right">Success@1</th>
                        <th class="text-right">Pass@3</th>
                        <th class="text-right">Mean Score</th>
                        <th class="text-right">Trials</th>
                        <th class="text-right">Cost / Pass</th>
                        <th class="text-right">Latency (p50 / p95)</th>
                        <th class="text-right">Violation Rate</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(agent_rows_html) if agent_rows_html else '<tr><td colspan="10" class="text-center text-muted">No agent runs recorded yet.</td></tr>'}
                </tbody>
            </table>
        </section>

        <section>
            <h2>Task Diagnostic Overview</h2>
            <table>
                <thead>
                    <tr>
                        <th>Task ID</th>
                        <th class="text-right">Total Attempts</th>
                        <th class="text-right">Passed</th>
                        <th class="text-right">Solve Rate</th>
                        <th class="text-right">Avg Score</th>
                        <th class="text-right">Avg Latency</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(task_rows_html) if task_rows_html else '<tr><td colspan="6" class="text-center text-muted">No benchmark tasks evaluated.</td></tr>'}
                </tbody>
            </table>
        </section>

        <section>
            <h2>Recent Execution History</h2>
            <input type="text" id="runSearch" class="search-box" placeholder="Filter by agent or task..." onkeyup="filterRuns()">
            <table id="runsTable">
                <thead>
                    <tr>
                        <th>Run ID</th>
                        <th>Task</th>
                        <th>Agent</th>
                        <th>Status</th>
                        <th class="text-right">Score</th>
                        <th class="text-right">Duration</th>
                        <th>Safety</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(run_rows_html) if run_rows_html else '<tr><td colspan="8" class="text-center text-muted">No execution history recorded.</td></tr>'}
                </tbody>
            </table>
        </section>
    </div>

    <script>
        function filterRuns() {{
            const input = document.getElementById("runSearch").value.toLowerCase();
            const rows = document.querySelectorAll(".run-row");
            rows.forEach(row => {{
                const agent = row.getAttribute("data-agent").toLowerCase();
                const task = row.getAttribute("data-task").toLowerCase();
                if (agent.includes(input) || task.includes(input)) {{
                    row.style.display = "";
                }} else {{
                    row.style.display = "none";
                }}
            }});
        }}
    </script>
</body>
</html>
"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_content, encoding="utf-8")
    return out
