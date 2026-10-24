"""End-to-end benchmark run orchestrator with Docker, security integrity, and regression tracking."""

import logging
import shutil
import tempfile
import time
from pathlib import Path

from agentbench.agent_adapter import (
    AgentAdapter,
    AgentResult,
    TaskEnvironment,
    get_agent,
)
from agentbench.artifacts import save_run_artifacts
from agentbench.cleanup import CleanupManager
from agentbench.docker_manager import DockerManager
from agentbench.evaluator import BaselineResult, EvaluationOutcome, Evaluator
from agentbench.models import (
    AgentReportInfo,
    BenchmarkReport,
    BenchmarkTask,
    FailureClassification,
    RunStatus,
)
from agentbench.reporting import save_report
from agentbench.scoring import Scorer
from agentbench.task_loader import load_task, validate_task_integrity
from agentbench.workspace import Workspace

logger = logging.getLogger("agentbench.runner")


class BenchmarkRunner:
    """Executes the full benchmark evaluation lifecycle."""

    def __init__(
        self,
        benchmarks_dir: str | Path = "benchmarks",
        results_dir: str | Path = "results",
        use_docker: bool = False,
    ) -> None:
        self.benchmarks_dir = Path(benchmarks_dir)
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.use_docker = use_docker
        self.cleanup_manager = CleanupManager()

    def _prepare_workspace(self, task: BenchmarkTask, run_id: str) -> Path:
        """Create a disposable, isolated host directory initialized with broken app state."""
        workspace_dir = Path(tempfile.mkdtemp(prefix=f"agentbench_{task.id}_{run_id}_"))
        self.cleanup_manager.register_directory(workspace_dir)

        # Copy application source code
        assert task.task_dir is not None
        app_src = task.task_dir / "app"
        app_dst = workspace_dir / "app"
        shutil.copytree(app_src, app_dst)

        # Copy broken configuration fixture as target file (.env or app/main.py)
        fixture_file = task.task_dir / (
            task.fault.fixture_file or "fixtures/broken.env"
        )
        target_name = task.fault.target_file or ".env"
        if fixture_file.is_file():
            shutil.copyfile(fixture_file, workspace_dir / target_name)

        return workspace_dir

    def run(
        self,
        task_id: str,
        agent_name: str = "scripted",
        run_id: str | None = None,
    ) -> BenchmarkReport:
        """Run the end-to-end benchmark for a task and agent with full observability."""
        start_time = time.time()
        run_id = run_id or f"run-{task_id[:16]}-{int(time.time())}"

        # 1. Load and validate task definition
        task = load_task(task_id, self.benchmarks_dir)
        integrity_errors = validate_task_integrity(task)
        if integrity_errors:
            err_msg = "; ".join(integrity_errors)
            return BenchmarkReport(
                run_id=run_id,
                task_id=task.id,
                task_version=task.version,
                status=RunStatus.INFRASTRUCTURE_ERROR,
                failure_classification=FailureClassification.INFRASTRUCTURE_FAILURE,
                score=0.0,
                duration_seconds=round(time.time() - start_time, 2),
                agent=AgentReportInfo(
                    name=agent_name,
                    tool_calls=0,
                    termination_reason="infrastructure_error",
                    summary="Task integrity validation failed",
                ),
                criteria={},
                error=err_msg,
            )

        workspace_dir: Path | None = None
        evaluator = Evaluator()
        container = None
        docker_mgr: DockerManager | None = None
        container_logs = ""

        try:
            # 2. Build or verify Docker image if Docker mode is active
            if self.use_docker:
                try:
                    docker_mgr = DockerManager()
                    docker_mgr.build_image(task)
                except Exception as e:
                    return BenchmarkReport(
                        run_id=run_id,
                        task_id=task.id,
                        task_version=task.version,
                        status=RunStatus.INFRASTRUCTURE_ERROR,
                        failure_classification=FailureClassification.INFRASTRUCTURE_FAILURE,
                        score=0.0,
                        duration_seconds=round(time.time() - start_time, 2),
                        agent=AgentReportInfo(
                            name=agent_name,
                            tool_calls=0,
                            termination_reason="docker_error",
                            summary="Docker image build failed",
                        ),
                        criteria={},
                        error=f"Docker error: {e}",
                    )

            # 3. Create isolated workspace and snapshot file integrity
            workspace_dir = self._prepare_workspace(task, run_id)
            ws_obj = Workspace(workspace_dir)

            # Record initial baseline pass statuses for regression detection
            pre_eval = evaluator.evaluate(task, workspace_dir)
            baseline_passes = {k: v.passed for k, v in pre_eval.criteria.items()}

            # If Docker mode: start container with workspace mounted
            if self.use_docker and docker_mgr:
                try:
                    container = docker_mgr.create_container(
                        task=task,
                        run_id=run_id,
                        workspace_dir=workspace_dir,
                        command_override=["tail", "-f", "/dev/null"],
                    )
                    self.cleanup_manager.register_container(container)
                except Exception as e:
                    return BenchmarkReport(
                        run_id=run_id,
                        task_id=task.id,
                        task_version=task.version,
                        status=RunStatus.INFRASTRUCTURE_ERROR,
                        failure_classification=FailureClassification.INFRASTRUCTURE_FAILURE,
                        score=0.0,
                        duration_seconds=round(time.time() - start_time, 2),
                        agent=AgentReportInfo(
                            name=agent_name,
                            tool_calls=0,
                            termination_reason="container_start_error",
                            summary="Failed to start isolated container",
                        ),
                        criteria={},
                        error=str(e),
                    )

            # 4. Verify initial broken state
            if self.use_docker and docker_mgr and container:
                exit_code, _, stderr = docker_mgr.exec_command(
                    container=container,
                    command=[
                        "python",
                        "-c",
                        "from app.settings import Settings; Settings()",
                    ],
                )
                if exit_code == 0:
                    baseline = BaselineResult(
                        is_valid=False,
                        reason="Initial state in container is healthy; fault not active.",
                    )
                else:
                    baseline = BaselineResult(
                        is_valid=True,
                        reason="Initial configuration fault verified inside container.",
                        error_output=stderr,
                    )
            else:
                baseline = evaluator.verify_initial_state(task, workspace_dir)

            if not baseline.is_valid:
                return BenchmarkReport(
                    run_id=run_id,
                    task_id=task.id,
                    task_version=task.version,
                    status=RunStatus.INFRASTRUCTURE_ERROR,
                    failure_classification=FailureClassification.INFRASTRUCTURE_FAILURE,
                    score=0.0,
                    duration_seconds=round(time.time() - start_time, 2),
                    agent=AgentReportInfo(
                        name=agent_name,
                        tool_calls=0,
                        termination_reason="baseline_error",
                        summary="Baseline verification failed: initial state not broken as expected",
                    ),
                    criteria={},
                    error=baseline.reason,
                )

            # 5. Initialize agent adapter and task environment
            agent: AgentAdapter = get_agent(agent_name)
            task_env = TaskEnvironment(ws_obj, task)

            # 6. Execute agent solve loop within budgets
            agent_result: AgentResult
            try:
                agent_result = agent.solve(task, task_env)
            except Exception as e:
                agent_result = AgentResult(
                    success=False,
                    duration_seconds=round(time.time() - start_time, 2),
                    tool_calls=task_env.tool_call_count,
                    summary="Agent crashed during solve",
                    error=str(e),
                    termination_reason="error",
                )

            # 7. Check anti-tamper filesystem integrity
            security_violations = ws_obj.check_integrity_violations()
            if ws_obj.security_violations:
                security_violations.extend(ws_obj.security_violations)
            security_violations = sorted(list(set(security_violations)))

            # 8. Run trusted evaluator with regression-aware tracking
            evaluation: EvaluationOutcome
            try:
                if self.use_docker and docker_mgr and container:
                    c_out, c_err = docker_mgr.collect_logs(container)
                    container_logs = f"STDOUT:\n{c_out}\nSTDERR:\n{c_err}"

                evaluation = evaluator.evaluate(
                    task=task,
                    workspace_dir=workspace_dir,
                    baseline_passes=baseline_passes,
                )
            except Exception as e:
                return BenchmarkReport(
                    run_id=run_id,
                    task_id=task.id,
                    task_version=task.version,
                    status=RunStatus.EVALUATOR_ERROR,
                    failure_classification=FailureClassification.INFRASTRUCTURE_FAILURE,
                    score=0.0,
                    duration_seconds=round(time.time() - start_time, 2),
                    agent=AgentReportInfo(
                        name=agent.name,
                        tool_calls=agent_result.tool_calls,
                        termination_reason=agent_result.termination_reason,
                        summary=agent_result.summary,
                    ),
                    criteria={},
                    error=f"Evaluator error: {e}",
                )

            # 9. Classify failure taxonomy
            final_status = Scorer.classify_status(
                score=evaluation.total_score,
                pass_threshold=task.evaluation.pass_threshold,
                timed_out=(agent_result.termination_reason == "timeout"),
            )

            if security_violations:
                failure_cls = FailureClassification.SECURITY_VIOLATION
                final_status = RunStatus.FAILED
                evaluation.total_score = 0.0
            elif evaluation.regression_detected:
                failure_cls = FailureClassification.REGRESSION_VIOLATION
            elif final_status == RunStatus.TIMEOUT:
                failure_cls = FailureClassification.TIMEOUT_EXCEEDED
            elif final_status in (RunStatus.FAILED, RunStatus.PARTIAL):
                if agent_result.error:
                    failure_cls = FailureClassification.PATCH_SYNTAX_ERROR
                else:
                    failure_cls = FailureClassification.FUNCTIONAL_FAILURE
            else:
                failure_cls = FailureClassification.NONE

            # 10. Extract Dual-Clock and Cost Metrics
            clock_obj = getattr(agent, "clock", None)
            if clock_obj and hasattr(clock_obj, "get_metrics"):
                cm = clock_obj.get_metrics()
                cost_usd = cm.estimated_cost_usd
                in_tok = cm.input_tokens
                out_tok = cm.output_tokens
                tot_tok = cm.total_tokens
                inf_lat = cm.inference_duration_seconds
                exec_lat = cm.execution_duration_seconds
            else:
                cost_usd = 0.0
                in_tok = 0
                out_tok = 0
                tot_tok = 0
                inf_lat = 0.0
                exec_lat = round(time.time() - start_time, 2)

            # 11. Collect artifacts
            artifacts = save_run_artifacts(
                run_id=run_id,
                results_dir=self.results_dir,
                agent_logs=f"Summary: {agent_result.summary}\nHistory: {agent_result.history}",
                evaluator_logs=evaluation.test_logs,
                container_logs=container_logs,
                patch_content=agent_result.patch_applied,
            )

            # 12. Generate and persist structured report
            report = BenchmarkReport(
                run_id=run_id,
                task_id=task.id,
                task_version=task.version,
                status=final_status,
                failure_classification=failure_cls,
                score=evaluation.total_score,
                duration_seconds=round(time.time() - start_time, 2),
                agent=AgentReportInfo(
                    name=agent.name,
                    tool_calls=agent_result.tool_calls,
                    termination_reason=agent_result.termination_reason,
                    summary=agent_result.summary,
                    temperature=task.agent.temperature,
                    seed=task.agent.seed,
                ),
                criteria=evaluation.criteria,
                artifacts=artifacts,
                environment={
                    "docker_enabled": self.use_docker,
                    "python_version": "3.12",
                    "category": task.category,
                    "difficulty": task.difficulty,
                },
                error=agent_result.error,
                cost_usd=cost_usd,
                input_tokens=in_tok,
                output_tokens=out_tok,
                total_tokens=tot_tok,
                inference_latency_seconds=inf_lat,
                execution_latency_seconds=exec_lat,
                security_violations=security_violations,
                regression_detected=evaluation.regression_detected,
            )

            save_report(report, self.results_dir)

            try:
                from agentbench.leaderboard import ExperimentTracker

                ExperimentTracker(self.results_dir / "experiments_index.json").record(
                    report
                )
            except Exception as e:
                logger.warning("Failed to record experiment index: %s", e)

            return report

        finally:
            self.cleanup_manager.cleanup()
