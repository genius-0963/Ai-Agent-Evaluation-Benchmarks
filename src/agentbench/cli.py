"""Command Line Interface for agentbench."""

import argparse
import json
import sys
from pathlib import Path

from agentbench import __version__
from agentbench.docker_manager import DockerManager
from agentbench.evaluator import Evaluator
from agentbench.models import RunStatus
from agentbench.reporting import format_terminal_summary, load_report
from agentbench.runner import BenchmarkRunner
from agentbench.task_loader import (
    TaskLoadError,
    list_tasks,
    load_task,
    validate_task_integrity,
)


def print_error(msg: str) -> None:
    sys.stderr.write(f"\033[91m[ERROR]\033[0m {msg}\n")


def print_success(msg: str) -> None:
    sys.stdout.write(f"\033[92m[SUCCESS]\033[0m {msg}\n")


def print_info(msg: str) -> None:
    sys.stdout.write(f"\033[94m[INFO]\033[0m {msg}\n")


def cmd_list(args: argparse.Namespace) -> int:
    """List all available benchmark tasks."""
    tasks = list_tasks(args.benchmarks_dir)
    if not tasks:
        print_info(f"No benchmark tasks found in '{args.benchmarks_dir}'.")
        return 0

    print("=" * 80)
    print(f"{'TASK ID':<25} {'VERSION':<10} {'PASS REQ':<10} {'NAME':<30}")
    print("-" * 80)
    for t in tasks:
        print(
            f"{t.id:<25} {t.version:<10} {t.evaluation.pass_threshold:<10.0f} {t.name:<30}"
        )
    print("=" * 80)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate task definition and related workspace assets."""
    try:
        task = load_task(args.task_id, args.benchmarks_dir)
    except TaskLoadError as e:
        print_error(f"Task loading error: {e}")
        return 2

    errors = validate_task_integrity(task)
    if errors:
        print_error(f"Task '{args.task_id}' failed validation checks:")
        for err in errors:
            print_error(f"  • {err}")
        return 2

    print_success(
        f"Task '{args.task_id}' (v{task.version}) passed all integrity validations."
    )
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Build the Docker container image for a benchmark task."""
    try:
        task = load_task(args.task_id, args.benchmarks_dir)
    except TaskLoadError as e:
        print_error(f"Task loading error: {e}")
        return 2

    print_info(f"Connecting to Docker daemon and building image for '{task.id}'...")
    try:
        dm = DockerManager()
        tag = dm.build_image(task, force_rebuild=args.force)
        print_success(f"Successfully built Docker image: {tag}")
        return 0
    except Exception as e:
        print_error(f"Image build failed: {e}")
        return 3


def cmd_smoke_test(args: argparse.Namespace) -> int:
    """Run an initialization smoke test verifying Docker and initial broken fault state."""
    try:
        task = load_task(args.task_id, args.benchmarks_dir)
    except TaskLoadError as e:
        print_error(f"Task loading error: {e}")
        return 2

    print_info(f"Running smoke test on task '{task.id}'...")
    try:
        dm = DockerManager()
        dm.build_image(task)
        container = dm.create_container(
            task=task,
            run_id="smoketest",
            command_override=["tail", "-f", "/dev/null"],
        )
        try:
            # Check fault reproducibility inside container
            code, out, err = dm.exec_command(
                container=container,
                command=[
                    "python",
                    "-c",
                    "from app.settings import Settings; Settings()",
                ],
            )
            if code != 0:
                print_success(
                    "Smoke test passed: Initial fault verified inside container."
                )
                return 0
            else:
                print_error(
                    "Smoke test failed: Initial container unexpectedly succeeded."
                )
                return 1
        finally:
            dm.cleanup(container)
    except Exception as e:
        print_error(f"Smoke test encountered error: {e}")
        return 3


def cmd_run(args: argparse.Namespace) -> int:
    """Execute end-to-end benchmark run."""
    print_info(f"Starting run for task '{args.task_id}' with agent '{args.agent}'...")
    runner = BenchmarkRunner(
        benchmarks_dir=args.benchmarks_dir,
        results_dir=args.results_dir,
        use_docker=args.docker,
    )

    report = runner.run(
        task_id=args.task_id,
        agent_name=args.agent,
        run_id=args.run_id,
    )

    # Output formatted report
    print()
    print(format_terminal_summary(report))
    print()

    if report.status == RunStatus.PASSED:
        print_success(f"Benchmark PASSED with score {report.score:.1f}/100.0!")
        return 0
    else:
        print_error(
            f"Benchmark finished with status {report.status.value.upper()} (score: {report.score:.1f})."
        )
        return 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    """Evaluate a workspace directory directly."""
    try:
        task = load_task(args.task_id, args.benchmarks_dir)
    except TaskLoadError as e:
        print_error(f"Task loading error: {e}")
        return 2

    workspace_dir = Path(args.workspace).resolve()
    if not workspace_dir.is_dir():
        print_error(f"Workspace directory not found: {workspace_dir}")
        return 2

    print_info(f"Evaluating workspace '{workspace_dir}' for task '{task.id}'...")
    evaluator = Evaluator()
    outcome = evaluator.evaluate(task, workspace_dir)

    print("=" * 60)
    print("EVALUATION OUTCOME:")
    for crit, det in outcome.criteria.items():
        box = "[PASS]" if det.passed else "[FAIL]"
        print(f"  • {crit:<15} {box:<6} {det.score:>4.1f} / {det.weight:<4.1f} pts")
    print(f"Total Score: {outcome.total_score:.1f} / 100.0")
    print("=" * 60)

    return 0 if outcome.success else 1


def cmd_matrix(args: argparse.Namespace) -> int:
    """Execute comparative benchmark matrix across multiple agents and tasks."""
    from agentbench.matrix import MatrixRunner

    print_info("Starting Benchmark Matrix Execution...")
    task_ids = [t.strip() for t in args.tasks.split(",")] if args.tasks else None
    agent_names = [a.strip() for a in args.agents.split(",")] if args.agents else None

    runner = MatrixRunner(
        benchmarks_dir=args.benchmarks_dir,
        results_dir=args.results_dir,
        use_docker=args.docker,
    )

    results = runner.run_matrix(task_ids=task_ids, agent_names=agent_names)
    summaries = runner.compute_leaderboard(results)

    print()
    print(runner.format_matrix_table(results))
    print()
    print(runner.format_leaderboard_table(summaries))
    print()

    # Exit code: 0 if at least one passed, 1 if all failed
    any_passed = any(s.tasks_passed > 0 for s in summaries)
    return 0 if any_passed else 1


def cmd_report(args: argparse.Namespace) -> int:
    """Display or export an existing report."""
    results_dir = Path(args.results_dir)
    target = args.report_id_or_path
    report_file = Path(target)

    if not report_file.is_file():
        # Check in results dir
        candidate = results_dir / f"{target}.json"
        if candidate.is_file():
            report_file = candidate
        else:
            print_error(f"Report file not found: {target}")
            return 2

    try:
        report = load_report(report_file)
    except Exception as e:
        print_error(f"Failed to load report {report_file}: {e}")
        return 2

    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
    else:
        print(format_terminal_summary(report))

    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Run repeated statistical trials and compute Pass@k and confidence intervals."""
    from agentbench.sdk import BenchmarkSDK

    k_values = (
        [int(k.strip()) for k in args.k.split(",") if k.strip().isdigit()]
        if args.k
        else None
    )

    sdk = BenchmarkSDK(benchmarks_dir=args.benchmarks_dir, results_dir=args.results_dir)
    print_info(
        f"Executing {args.trials} evaluation trials for '{args.task_id}' with agent '{args.agent}'..."
    )

    try:
        summary = sdk.evaluate_task(
            task_id=args.task_id,
            agent_name=args.agent,
            trials=args.trials,
            k_values=k_values,
            use_docker=args.docker,
        )
    except Exception as e:
        print_error(f"Evaluation failed: {e}")
        return 1

    print()
    print("=" * 70)
    print(f"STATISTICAL EVALUATION SUMMARY: {summary.task_id} ({summary.agent_name})")
    print("=" * 70)
    print(f"Trials Executed:         {summary.trials_count}")
    print(f"Successful Passes:       {summary.success_count}/{summary.trials_count}")
    print(f"Success@1:               {summary.success_at_1 * 100:.1f}%")
    for k, val in summary.pass_at_k.items():
        print(f"Pass@{k}:                  {val * 100:.1f}%")
    print("-" * 70)
    print(f"Mean Score:              {summary.mean_score:.1f} / 100")
    print(
        f"Score Variance (Std):    {summary.score_variance:.2f} (±{summary.score_std_dev:.2f})"
    )
    print(
        f"95% Confidence Interval: [{summary.confidence_interval_95[0]:.1f}, {summary.confidence_interval_95[1]:.1f}]"
    )
    print("-" * 70)
    print(
        f"Latency (Median / p95):   {summary.median_latency_seconds:.2f}s / {summary.p95_latency_seconds:.2f}s"
    )
    print(
        f"Mean Inf / Exec Time:    {summary.mean_inference_latency_seconds:.2f}s / {summary.mean_execution_latency_seconds:.2f}s"
    )
    print(f"Total Cost (USD):        ${summary.total_cost_usd:.4f}")
    print(f"Cost / Successful Pass:  ${summary.cost_per_successful_pass_usd:.4f}")
    print(f"Violation Rate:          {summary.violation_rate * 100:.1f}%")
    print(f"Regression Rate:         {summary.regression_rate * 100:.1f}%")
    print("=" * 70)
    print()

    return 0 if summary.success_count > 0 else 1


def cmd_leaderboard(args: argparse.Namespace) -> int:
    """Generate HTML and Markdown leaderboards from historical experiment index."""
    from agentbench.leaderboard import (
        ExperimentTracker,
        generate_html_leaderboard,
        generate_markdown_leaderboard,
    )

    tracker = ExperimentTracker(Path(args.results_dir) / "experiments_index.json")
    experiments = tracker.load_all()

    if not experiments:
        print_info(
            f"No experiments found in {tracker.index_path}. Run tasks or matrices first."
        )
        return 0

    html_path = Path(args.output_html)
    md_path = Path(args.output_md)

    generate_html_leaderboard(experiments, output_path=html_path)
    generate_markdown_leaderboard(experiments, output_path=md_path)

    print_success(f"Generated HTML leaderboard: {html_path}")
    print_success(f"Generated Markdown leaderboard: {md_path}")
    return 0


def cmd_scaffold(args: argparse.Namespace) -> int:
    """Scaffold a new benchmark task with manifest, fixtures, app, tests, and Dockerfile."""
    from agentbench.sdk import BenchmarkSDK

    sdk = BenchmarkSDK(benchmarks_dir=args.benchmarks_dir)
    try:
        path = sdk.create_task(
            task_id=args.task_id,
            name=args.name,
            category=args.category,
            difficulty=args.difficulty,
            overwrite=args.force,
        )
        print_success(f"Successfully scaffolded benchmark '{args.task_id}' at {path}")
        return 0
    except Exception as e:
        print_error(f"Failed to scaffold task: {e}")
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="agentbench",
        description="ai-agent-evaluation-benchmarks: Reproducible benchmarks for AI software-repair agents",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--benchmarks-dir", default="benchmarks", help="Path to benchmarks directory"
    )
    parser.add_argument(
        "--results-dir", default="results", help="Path to results directory"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List available benchmark tasks")
    p_list.set_defaults(func=cmd_list)

    # validate
    p_val = subparsers.add_parser("validate", help="Validate task metadata and files")
    p_val.add_argument("task_id", help="Task ID or folder name")
    p_val.set_defaults(func=cmd_validate)

    # build
    p_build = subparsers.add_parser("build", help="Build the Docker image for a task")
    p_build.add_argument("task_id", help="Task ID or folder name")
    p_build.add_argument(
        "--force", action="store_true", help="Force rebuild image without cache"
    )
    p_build.set_defaults(func=cmd_build)

    # smoke-test
    p_smoke = subparsers.add_parser(
        "smoke-test", help="Check Docker and task initialization"
    )
    p_smoke.add_argument("task_id", help="Task ID or folder name")
    p_smoke.set_defaults(func=cmd_smoke_test)

    # run
    p_run = subparsers.add_parser("run", help="Run an end-to-end benchmark")
    p_run.add_argument("task_id", help="Task ID or folder name")
    p_run.add_argument(
        "--agent", default="scripted", help="Agent adapter (scripted, no-op, llm)"
    )
    p_run.add_argument(
        "--docker", action="store_true", help="Execute containerized inside Docker"
    )
    p_run.add_argument("--run-id", default=None, help="Explicit custom run ID")
    p_run.set_defaults(func=cmd_run)

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Evaluate a workspace directory")
    p_eval.add_argument("task_id", help="Task ID")
    p_eval.add_argument(
        "--workspace", required=True, help="Path to workspace directory"
    )
    p_eval.set_defaults(func=cmd_evaluate)

    # report
    p_rep = subparsers.add_parser("report", help="Display or export a report")
    p_rep.add_argument("report_id_or_path", help="Run ID or path to JSON report file")
    p_rep.add_argument(
        "--json", action="store_true", help="Output raw JSON instead of table"
    )
    p_rep.set_defaults(func=cmd_report)

    # matrix
    p_mat = subparsers.add_parser(
        "matrix", help="Run combinatorial benchmark matrix across tasks and agents"
    )
    p_mat.add_argument(
        "--tasks", default="all", help="Comma-separated task IDs or 'all'"
    )
    p_mat.add_argument(
        "--agents", default="scripted,noop,llm", help="Comma-separated agent names"
    )
    p_mat.add_argument(
        "--docker", action="store_true", help="Run within Docker containers"
    )
    p_mat.set_defaults(func=cmd_matrix)

    # eval (repeated statistical trials)
    p_eval_stat = subparsers.add_parser(
        "eval",
        help="Run repeated trials and calculate Pass@k, variance & confidence intervals",
    )
    p_eval_stat.add_argument("task_id", help="Task ID or folder name")
    p_eval_stat.add_argument(
        "--agent", default="scripted", help="Agent adapter (scripted, no-op, llm)"
    )
    p_eval_stat.add_argument(
        "--trials", type=int, default=3, help="Number of evaluation trials to run"
    )
    p_eval_stat.add_argument(
        "-k",
        "--k",
        default="1,3",
        help="Comma-separated k values for Pass@k (e.g. '1,3,5')",
    )
    p_eval_stat.add_argument(
        "--docker", action="store_true", help="Execute trials inside Docker containers"
    )
    p_eval_stat.set_defaults(func=cmd_eval)

    # leaderboard
    p_lead = subparsers.add_parser(
        "leaderboard", help="Generate public HTML and Markdown leaderboards"
    )
    p_lead.add_argument(
        "--output-html",
        default="results/leaderboard.html",
        help="Path for generated HTML dashboard",
    )
    p_lead.add_argument(
        "--output-md",
        default="results/LEADERBOARD.md",
        help="Path for generated Markdown leaderboard",
    )
    p_lead.set_defaults(func=cmd_leaderboard)

    # scaffold
    p_scaf = subparsers.add_parser(
        "scaffold", help="Scaffold a new benchmark task via the Contributor SDK"
    )
    p_scaf.add_argument(
        "task_id", help="New task ID (e.g., redis-cluster-failover-001)"
    )
    p_scaf.add_argument("--name", default=None, help="Human-readable task name")
    p_scaf.add_argument(
        "--category", default="api_reliability", help="Benchmark category"
    )
    p_scaf.add_argument(
        "--difficulty", default="medium", help="Difficulty (easy, medium, hard)"
    )
    p_scaf.add_argument(
        "--force", action="store_true", help="Overwrite existing task directory"
    )
    p_scaf.set_defaults(func=cmd_scaffold)

    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
