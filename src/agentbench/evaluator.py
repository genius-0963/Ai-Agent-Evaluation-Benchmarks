"""Independent evaluator executing trusted pytest checks against the repaired service."""

import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from agentbench.models import BenchmarkTask, CriterionDetail

logger = logging.getLogger("agentbench.evaluator")


@dataclass
class BaselineResult:
    """Outcome of pre-run baseline verification."""

    is_valid: bool
    reason: str
    error_output: str = ""


@dataclass
class CriterionOutcome:
    """Individual criterion evaluation result."""

    name: str
    weight: float
    passed: bool
    score: float
    details: str = ""


@dataclass
class EvaluationOutcome:
    """Aggregated evaluation outcome across all test criteria."""

    success: bool
    total_score: float
    criteria: dict[str, CriterionDetail] = field(default_factory=dict)
    test_logs: str = ""
    error: str | None = None
    regression_detected: bool = False
    regressed_modules: list[str] = field(default_factory=list)


class Evaluator:
    """Executes trusted tests and grades the repaired workspace."""

    CRITERIA_MODULE_MAP = {
        "configuration": "test_configuration.py",
        "startup": "test_service_health.py",
        "behavior": "test_behavior.py",
        "regression": "test_regression.py",
    }

    def __init__(self, python_executable: str | None = None) -> None:
        self.python_executable = python_executable or sys.executable

    def verify_initial_state(
        self, task: BenchmarkTask, workspace_dir: Path
    ) -> BaselineResult:
        """Verify that the initial environment is broken for the expected reason."""
        if task.fault.type == "schema_contract_violation":
            passed, out = self.evaluate_criterion_module(
                task=task,
                workspace_dir=workspace_dir,
                module_name="test_behavior.py",
            )
            if not passed:
                return BaselineResult(
                    is_valid=True,
                    reason="Initial contract violation verified successfully.",
                    error_output=out,
                )
            else:
                return BaselineResult(
                    is_valid=False,
                    reason="Initial state unexpectedly passed contract checks; fault not active.",
                )

        # Default configuration check
        env_file = workspace_dir / (task.fault.target_file or ".env")
        if not env_file.is_file():
            return BaselineResult(
                is_valid=False,
                reason="Fault verification failed: target configuration file not found.",
            )

        check_cmd = [
            self.python_executable,
            "-c",
            (
                "import os, sys;\n"
                f"os.environ['BENCH_CONFIG_FILE'] = r'{env_file}';\n"
                "os.environ.pop('BENCH_CATALOG_ITEMS', None);\n"
                "sys.path.insert(0, r'" + str(workspace_dir) + "');\n"
                "try:\n"
                "    from app.settings import Settings;\n"
                "    Settings();\n"
                "    sys.exit(0);\n"
                "except Exception as e:\n"
                "    sys.stderr.write(str(e));\n"
                "    sys.exit(42);\n"
            ),
        ]

        try:
            res = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(workspace_dir),
            )
            if res.returncode == 42:
                # Broken as expected
                return BaselineResult(
                    is_valid=True,
                    reason="Initial configuration fault verified successfully.",
                    error_output=res.stderr,
                )
            elif res.returncode == 0:
                return BaselineResult(
                    is_valid=False,
                    reason="Initial state is unexpectedly healthy; benchmark fault not active.",
                )
            else:
                return BaselineResult(
                    is_valid=False,
                    reason=f"Unexpected failure during initial verification: code {res.returncode}",
                    error_output=res.stderr,
                )
        except Exception as e:
            return BaselineResult(
                is_valid=False,
                reason=f"Baseline verification error: {e}",
                error_output=str(e),
            )

    def evaluate_criterion_module(
        self,
        task: BenchmarkTask,
        workspace_dir: Path,
        module_name: str,
        base_url: str | None = None,
    ) -> tuple[bool, str]:
        """Run a single test module from the trusted benchmark tests directory."""
        if not task.task_dir:
            return False, "Task directory is not set."

        test_file = task.task_dir / task.evaluation.tests_directory / module_name
        if not test_file.is_file():
            return False, f"Test module '{module_name}' missing from benchmark."

        # Evaluator environment variables
        env = os.environ.copy()
        env["EVAL_WORKSPACE_PATH"] = str(workspace_dir.resolve())
        env["PYTHONPATH"] = (
            str(workspace_dir.resolve()) + os.pathsep + str(task.task_dir)
        )
        if base_url:
            env["EVAL_BASE_URL"] = base_url

        cmd = [
            self.python_executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            "--tb=short",
            "-q",
        ]

        try:
            res = subprocess.run(
                cmd,
                cwd=str(workspace_dir),
                capture_output=True,
                text=True,
                env=env,
                timeout=task.environment.execution_timeout_seconds,
            )
            passed = res.returncode == 0
            output = res.stdout + ("\n" + res.stderr if res.stderr else "")
            return passed, output
        except subprocess.TimeoutExpired:
            return (
                False,
                f"Test module {module_name} timed out after {task.environment.execution_timeout_seconds}s",
            )
        except Exception as e:
            return False, f"Evaluator execution failed for {module_name}: {e}"

    def evaluate(
        self,
        task: BenchmarkTask,
        workspace_dir: Path,
        base_url: str | None = None,
        baseline_passes: dict[str, bool] | None = None,
    ) -> EvaluationOutcome:
        """Run all independent evaluation modules and compute criterion pass/fail statuses."""
        criteria_details: dict[str, CriterionDetail] = {}
        all_logs: list[str] = []
        weights = {
            "configuration": task.scoring.configuration,
            "startup": task.scoring.startup,
            "behavior": task.scoring.behavior,
            "regression": task.scoring.regression,
        }

        total_earned = 0.0
        current_passes: dict[str, bool] = {}

        for crit_name, module_filename in self.CRITERIA_MODULE_MAP.items():
            weight = weights.get(crit_name, 25.0)
            passed, test_log = self.evaluate_criterion_module(
                task=task,
                workspace_dir=workspace_dir,
                module_name=module_filename,
                base_url=base_url,
            )
            current_passes[crit_name] = passed
            score = weight if passed else 0.0
            total_earned += score
            criteria_details[crit_name] = CriterionDetail(
                weight=weight,
                passed=passed,
                score=score,
                details=f"Test module {module_filename} {'PASSED' if passed else 'FAILED'}",
            )
            all_logs.append(
                f"=== {crit_name.upper()} ({module_filename}) ===\n{test_log}"
            )

        # Regression-aware detection: Did any module that previously passed now fail?
        regression_detected = False
        regressed_modules: list[str] = []
        if baseline_passes:
            for crit_name, was_passed in baseline_passes.items():
                if was_passed and not current_passes.get(crit_name, False):
                    regression_detected = True
                    regressed_modules.append(crit_name)

        if regression_detected:
            # Penalize regression criterion if previous behavior regressed
            if "regression" in criteria_details:
                criteria_details["regression"].passed = False
                criteria_details["regression"].score = 0.0
                criteria_details[
                    "regression"
                ].details = f"Regression detected in previously passing checks: {', '.join(regressed_modules)}"
            total_earned = sum(c.score for c in criteria_details.values())

        return EvaluationOutcome(
            success=(
                total_earned >= task.evaluation.pass_threshold
                and not regression_detected
            ),
            total_score=round(total_earned, 2),
            criteria=criteria_details,
            test_logs="\n\n".join(all_logs),
            regression_detected=regression_detected,
            regressed_modules=regressed_modules,
        )
