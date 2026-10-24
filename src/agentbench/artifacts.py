"""Artifact collection and persistence for benchmark runs."""

from pathlib import Path


def save_run_artifacts(
    run_id: str,
    results_dir: Path,
    agent_logs: str = "",
    evaluator_logs: str = "",
    container_logs: str = "",
    patch_content: str | None = None,
) -> list[str]:
    """Write run logs and patch artifacts to disk, returning relative artifact paths."""
    run_artifacts_dir = results_dir / f"{run_id}_artifacts"
    run_artifacts_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[str] = []

    # Agent execution log
    if agent_logs:
        agent_log_path = run_artifacts_dir / "agent.log"
        agent_log_path.write_text(agent_logs, encoding="utf-8")
        saved_paths.append(str(agent_log_path))

    # Evaluator test output log
    if evaluator_logs:
        eval_log_path = run_artifacts_dir / "evaluator.log"
        eval_log_path.write_text(evaluator_logs, encoding="utf-8")
        saved_paths.append(str(eval_log_path))

    # Docker container logs
    if container_logs:
        container_log_path = run_artifacts_dir / "container.log"
        container_log_path.write_text(container_logs, encoding="utf-8")
        saved_paths.append(str(container_log_path))

    # Agent applied patch / diff
    if patch_content:
        patch_path = run_artifacts_dir / "patch.diff"
        patch_path.write_text(patch_content, encoding="utf-8")
        saved_paths.append(str(patch_path))

    return saved_paths
