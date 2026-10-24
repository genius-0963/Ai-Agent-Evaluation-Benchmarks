"""AgentBench Contributor SDK: Programmatic authoring, validation, packaging, and evaluation of benchmarks."""

import logging
import shutil
import tarfile
from pathlib import Path

from agentbench.runner import BenchmarkRunner
from agentbench.stats import StatisticalSummary, compute_statistical_summary
from agentbench.task_loader import load_task, validate_task_integrity

logger = logging.getLogger("agentbench.sdk")


class BenchmarkSDK:
    """Extensible SDK for benchmark authors and research teams."""

    def __init__(
        self,
        benchmarks_dir: str | Path = "benchmarks",
        results_dir: str | Path = "results",
    ) -> None:
        self.benchmarks_dir = Path(benchmarks_dir)
        self.results_dir = Path(results_dir)

    def create_task(
        self,
        task_id: str,
        name: str | None = None,
        category: str = "api_reliability",
        difficulty: str = "medium",
        overwrite: bool = False,
    ) -> Path:
        """Scaffold a production-grade benchmark task directory with manifest, app, tests, and Dockerfile."""
        task_id = task_id.strip().lower().replace("_", "-")
        target_dir = self.benchmarks_dir / task_id

        if target_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"Task directory '{target_dir}' already exists. Use overwrite=True to replace."
                )
            shutil.rmtree(target_dir)

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "app").mkdir(parents=True, exist_ok=True)
        (target_dir / "tests").mkdir(parents=True, exist_ok=True)
        (target_dir / "fixtures").mkdir(parents=True, exist_ok=True)

        display_name = name or task_id.replace("-", " ").title()

        # 1. Manifest (task.yaml)
        manifest_content = f"""id: "{task_id}"
name: "{display_name}"
version: "1.0.0"
category: "{category}"
difficulty: "{difficulty}"
description: >
  Diagnostic and repair benchmark for {display_name}.

environment:
  dockerfile: "Dockerfile"
  working_directory: "/workspace"
  startup_timeout_seconds: 30
  execution_timeout_seconds: 120
  memory_limit: "512m"
  memory_mb: 512
  cpus: 1.0
  cpu_cores: 1.0
  network_enabled: false
  network: "disabled"
  read_only_rootfs: false

fault:
  type: "runtime_exception"
  target_file: ".env"
  fixture_file: "fixtures/broken.env"
  repaired_fixture_file: "fixtures/repaired.env"
  description: "Service configuration error injected via environment variables"
  reset_procedure: "Copy fixtures/broken.env to .env"

agent:
  prompt_file: "prompt.md"
  tools:
    - read_file
    - write_file
    - list_files
    - search_code
    - run_command
  max_runtime_seconds: 300
  max_tool_calls: 40
  temperature: 0.0
  seed: 42

evaluation:
  tests_directory: "tests"
  pass_threshold: 80

scoring:
  configuration: 25
  startup: 25
  behavior: 25
  regression: 25

security:
  hidden_tests: true
  protect_evaluator: true
  randomized_inputs: true
  detect_filesystem_tampering: true
  read_only_rootfs: false

artifacts:
  - agent.log
  - patch.diff
  - evaluator.log
  - container.log
  - report.json
"""
        (target_dir / "task.yaml").write_text(manifest_content, encoding="utf-8")

        # 2. Agent Prompt (prompt.md)
        prompt_content = f"""# Task: {display_name}

The service is currently failing during execution or returning error responses.

## Symptoms
- Check service logs and examine configuration in `.env`.
- `GET /health` may be failing or downstream routes throw unexpected exceptions.

## Requirements
1. Inspect the source code under `app/` and the environment variables in `.env`.
2. Identify the root cause and apply the minimal correct patch.
3. Verify that the health endpoint and core business logic respond with HTTP 200.
4. Do not delete or tamper with tests or evaluator files.
"""
        (target_dir / "prompt.md").write_text(prompt_content, encoding="utf-8")

        # 3. Fixtures
        (target_dir / "fixtures/broken.env").write_text(
            "SERVICE_KEY=INVALID_VALUE\nPORT=8000\n", encoding="utf-8"
        )
        (target_dir / "fixtures/repaired.env").write_text(
            "SERVICE_KEY=VALID_SECRET\nPORT=8000\n", encoding="utf-8"
        )

        # 4. App Source
        (target_dir / "app/__init__.py").write_text("", encoding="utf-8")
        app_main_content = """import os
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Benchmark Target Service")

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/api/v1/data")
def get_data() -> dict[str, str]:
    key = os.getenv("SERVICE_KEY", "")
    if key != "VALID_SECRET":
        raise HTTPException(status_code=500, detail="Service key invalid")
    return {"status": "success", "data": "operational"}
"""
        (target_dir / "app/main.py").write_text(app_main_content, encoding="utf-8")

        # 5. Tests
        (target_dir / "tests/__init__.py").write_text("", encoding="utf-8")
        conftest_content = """import os
import sys
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient

@pytest.fixture(scope="session")
def workspace_path() -> Path:
    raw = os.getenv("EVAL_WORKSPACE_PATH")
    if raw:
        p = Path(raw).resolve()
        if p.is_dir():
            return p
    return Path(__file__).resolve().parent.parent

@pytest.fixture(scope="session")
def client(workspace_path: Path):
    base_url = os.getenv("EVAL_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=5.0) as http_client:
            yield http_client
        return

    workspace_str = str(workspace_path)
    if workspace_str not in sys.path:
        sys.path.insert(0, workspace_str)

    workspace_env = workspace_path / ".env"
    if workspace_env.is_file():
        os.environ["BENCH_CONFIG_FILE"] = str(workspace_env)
        # Load dotenv into os.environ
        for line in workspace_env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

    for mod in list(sys.modules.keys()):
        if mod.startswith("app"):
            sys.modules.pop(mod, None)

    try:
        from app.main import app
        with TestClient(app) as test_client:
            yield test_client
    finally:
        for mod in list(sys.modules.keys()):
            if mod.startswith("app"):
                sys.modules.pop(mod, None)
"""
        (target_dir / "tests/conftest.py").write_text(
            conftest_content, encoding="utf-8"
        )

        (target_dir / "tests/test_configuration.py").write_text(
            """def test_env_exists(workspace_path):
    env_file = workspace_path / ".env"
    assert env_file.is_file()
""",
            encoding="utf-8",
        )

        (target_dir / "tests/test_service_health.py").write_text(
            """def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
""",
            encoding="utf-8",
        )

        (target_dir / "tests/test_behavior.py").write_text(
            """def test_api_data(client):
    res = client.get("/api/v1/data")
    assert res.status_code == 200
    assert res.json().get("status") == "success"
""",
            encoding="utf-8",
        )

        (target_dir / "tests/test_regression.py").write_text(
            """def test_unknown_route(client):
    res = client.get("/api/v1/unknown")
    assert res.status_code == 404
""",
            encoding="utf-8",
        )

        # 6. Dockerfile
        dockerfile_content = """FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace

RUN useradd -m -u 1000 -s /bin/bash benchuser && \\
    mkdir -p /workspace && \\
    chown -R benchuser:benchuser /workspace

WORKDIR /workspace

RUN pip install --no-cache-dir \\
    "fastapi==0.115.0" \\
    "uvicorn==0.30.6" \\
    "httpx==0.27.2" \\
    "pytest==8.3.3"

COPY --chown=benchuser:benchuser app/ /workspace/app/
COPY --chown=benchuser:benchuser fixtures/broken.env /workspace/.env

USER benchuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
        (target_dir / "Dockerfile").write_text(dockerfile_content, encoding="utf-8")

        logger.info("Successfully scaffolded benchmark task at %s", target_dir)
        return target_dir

    def validate_task(self, task_id: str) -> list[str]:
        """Validate manifest, file structure, and test suite completeness."""
        task = load_task(task_id, self.benchmarks_dir)
        errors = validate_task_integrity(task)

        # Extended SDK checks
        task_dir = task.task_dir
        if not task_dir:
            return errors + ["Task directory reference is missing."]

        tests_dir = task_dir / task.evaluation.tests_directory
        expected_tests = [
            "test_configuration.py",
            "test_service_health.py",
            "test_behavior.py",
            "test_regression.py",
        ]
        for tf in expected_tests:
            if not (tests_dir / tf).is_file():
                errors.append(f"Missing recommended evaluator test module: {tf}")

        return errors

    def package_task(
        self,
        task_id: str,
        output_archive: str | Path | None = None,
    ) -> Path:
        """Package a benchmark into a compressed distribution archive (.tar.gz)."""
        errors = self.validate_task(task_id)
        if errors:
            raise ValueError(f"Cannot package invalid task '{task_id}': {errors}")

        task_dir = self.benchmarks_dir / task_id
        if not task_dir.is_dir():
            raise FileNotFoundError(f"Task directory '{task_dir}' not found.")

        out_path = Path(output_archive) if output_archive else Path(f"{task_id}.tar.gz")

        def _filter(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
            if (
                "__pycache__" in tarinfo.name
                or tarinfo.name.endswith(".pyc")
                or ".pytest_cache" in tarinfo.name
            ):
                return None
            return tarinfo

        with tarfile.open(out_path, "w:gz") as tar:
            tar.add(task_dir, arcname=task_id, filter=_filter)

        logger.info("Packaged task '%s' to %s", task_id, out_path)
        return out_path

    def evaluate_task(
        self,
        task_id: str,
        agent_name: str = "scripted",
        trials: int = 3,
        k_values: list[int] | None = None,
        use_docker: bool = False,
    ) -> StatisticalSummary:
        """Run repeated trials of a task and return aggregate statistical metrics."""
        runner = BenchmarkRunner(
            benchmarks_dir=self.benchmarks_dir,
            results_dir=self.results_dir,
            use_docker=use_docker,
        )

        reports = []
        for i in range(1, trials + 1):
            run_id = f"eval-{task_id[:12]}-{agent_name}-t{i}"
            logger.info("Executing trial %d/%d for task '%s'...", i, trials, task_id)
            report = runner.run(task_id=task_id, agent_name=agent_name, run_id=run_id)
            reports.append(report)

        return compute_statistical_summary(reports, k_values=k_values)
