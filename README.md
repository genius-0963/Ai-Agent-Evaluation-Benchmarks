# ai-agent-evaluation-benchmarks

[![CI Tests](https://github.com/example/ai-agent-evaluation-benchmarks/actions/workflows/tests.yml/badge.svg)](https://github.com/example/ai-agent-evaluation-benchmarks/actions)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python: >=3.12](https://img.shields.io/badge/python-3.12+-blue.svg)](pyproject.toml)

An open-source, Docker-based benchmark framework for evaluating AI coding agents on reproducible software-repair tasks using Python and pytest. Features isolated task environments, controlled configuration failures, independent grading, structured JSON evaluation reports, and provider-neutral agent adapters.

---

## 1. What the Framework Evaluates

Evaluating AI coding agents requires a disciplined, isolated environment where the failure mode is deterministic, the repair is verifiable, and evaluation tests cannot be tampered with by the agent.

`ai-agent-evaluation-benchmarks` tests an agent's ability to:
- **Inspect evidence**: Navigate workspaces, read configuration files, and search codebases using restricted diagnostic tools.
- **Diagnose root cause**: Identify semantic defects (such as invalid configuration syntax or schema mismatches) without relying on random trials.
- **Implement minimal appropriate repairs**: Fix the underlying issue without hardcoding outputs or breaking existing contracts.
- **Preserve API contracts & regressions**: Satisfy health and business behavior without introducing side effects or contract deviations.

---

## 2. Architecture and Run Lifecycle

```
Benchmark CLI (agentbench)
        │
        ▼
Python Harness / Task Loader
        │
        ├──► Docker Image Build & Container Lifecycle (cgroups, caps dropped, no socket)
        │
        ├──► Disposable Task Environment
        │       ├── Application source code
        │       ├── Deliberately broken configuration (.env)
        │       └── Agent-confined workspace (/workspace)
        │
        ├──► Agent Adapter Loop
        │       ├── Scripted baseline (pipeline verification)
        │       ├── No-op agent (grading integrity)
        │       └── LLM-backed agent (reasoning & tool-calling)
        │
        ├──► Independent Pytest Evaluator (Outside Agent Scope)
        │       ├── test_configuration.py  (30 pts)
        │       ├── test_service_health.py (20 pts)
        │       ├── test_behavior.py       (30 pts)
        │       └── test_regression.py     (20 pts)
        │
        ├──► Scoring & Structured Reporting (JSON Schema 1.0)
        │
        └──► Artifacts Collection & Guaranteed Cleanup (finally block)
```

### Execution Lifecycle:
1. **Load & Validate Task**: Parses `task.yaml`, checks `Dockerfile`, `prompt.md`, and test suite integrity.
2. **Build / Verify Image**: Uses pinned base image `python:3.12-slim` with dropped Linux capabilities and explicit limits.
3. **Spawn Disposable Container**: Applies memory limits (`512m`), CPU limits (`1.0`), PID limits (`150`), and network isolation (`network_mode="none"` by default).
4. **Baseline Verification**: Evaluates initial broken state. If the task is not broken for the intended reason, it is classified as `INFRASTRUCTURE_ERROR`.
5. **Solve Loop**: Passes `prompt.md` and sandboxed workspace tools (`read_file`, `write_file`, `list_files`, `search_text`, `run_allowed_command`) to the agent, enforcing tool and runtime budgets.
6. **Freeze Workspace & Independent Evaluation**: Executes the trusted, read-only pytest suite (`test_configuration`, `test_service_health`, `test_behavior`, `test_regression`).
7. **Score Calculation**: Computes earned points out of 100 and classifies run status (`passed`, `partial`, `failed`, `timeout`, `infrastructure_error`, `evaluator_error`).
8. **Artifact Collection & Report Generation**: Records agent thoughts, container logs, evaluator output, and unified diffs into `results/<run_id>.json`.
9. **Guaranteed Cleanup**: Destroys disposable containers and cleans temporary workspaces even upon timeouts or unexpected errors.

---

## 3. Installation & Quickstart

### Prerequisites:
- Python >= 3.12
- Docker Desktop or Docker Engine

### Quick Setup:
```bash
# Clone the repository
git clone https://github.com/example/ai-agent-evaluation-benchmarks.git
cd ai-agent-evaluation-benchmarks

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install package in editable mode with development dependencies
python -m pip install -e ".[dev]"

# Run unit tests to verify installation
pytest tests/unit -v
```

### Using the CLI (`agentbench`):
```bash
# 1. Discover benchmark tasks
agentbench list

# 2. Validate benchmark definition
agentbench validate config-recovery-001

# 3. Build task Docker image
agentbench build config-recovery-001

# 4. Run initialization smoke test
agentbench smoke-test config-recovery-001

# 5. Run end-to-end benchmark with scripted baseline agent
agentbench run config-recovery-001 --agent scripted --docker

# 6. Verify grading integrity with no-op agent (must fail)
agentbench run config-recovery-001 --agent noop

# 7. Run repeated statistical trials (Pass@k, confidence intervals)
agentbench eval multi-service-cache-001 --agent scripted --trials 5 -k 1,3,5

# 8. Export HTML and Markdown leaderboards
agentbench leaderboard --output-html results/leaderboard.html --output-md results/LEADERBOARD.md

# 9. Run combinatorial benchmark matrix
agentbench matrix --tasks all --agents scripted,noop

# 10. Scaffold a new benchmark with Contributor SDK
agentbench scaffold database-pool-leak-001 --category resource_leak --difficulty hard

# 11. View generated report
agentbench report <RUN_ID>
```

---

## 4. Docker Isolation & Security Model

Agent execution can be unpredictable. The evaluation harness enforces defense-in-depth:
- **No Docker Socket Mounting**: The Docker socket (`/var/run/docker.sock`) is never mounted inside agent environments.
- **Network Isolation**: Execution is disconnected from the host network (`network_mode="none"`) unless explicitly enabled.
- **Resource Constraints**: Strict limits on memory (`512MB`), CPU quotas (`1.0`), and maximum processes (`pids_limit=150`).
- **Least Privilege**: Runs as unprivileged user `benchuser` (UID 1000) with Linux capabilities dropped (`cap_drop=["ALL"]`) and `no-new-privileges:true`.
- **Path Escape Prevention**: All workspace tools validate canonical paths to prevent directory traversal (`../`) outside `/workspace`.
- **Evaluator Independence**: Evaluation test files reside outside the agent workspace; agents cannot modify test criteria or assertions.

---

## 5. Scoring Methodology

The framework uses a transparent 100-point weighted model across four distinct criteria:

| Criterion | Weight | Measured Capability | Test File |
| :--- | :--- | :--- | :--- |
| **Configuration** | **30 pts** | Valid settings structure, absence of syntax/schema errors | `test_configuration.py` |
| **Startup / Health**| **20 pts** | Service initialization and `/health` HTTP 200 response | `test_service_health.py` |
| **Behavior** | **30 pts** | Functional correctness (`/api/catalog`), configuration-driven response | `test_behavior.py` |
| **Regression** | **20 pts** | Preservation of existing API contracts and schema types | `test_regression.py` |

### Run Statuses:
- `passed`: Final score $\ge 80.0$ pts.
- `partial`: $0.0 < \text{score} < 80.0$ pts.
- `failed`: Score is $0.0$ pts (e.g. no changes made or service remained broken).
- `timeout`: Agent exceeded max runtime seconds.
- `infrastructure_error`: Failure in Docker daemon, image build, or baseline verification.
- `evaluator_error`: Failure in the evaluation execution engine.

---

## 6. How to Add a Benchmark

1. Create a directory under `benchmarks/<task-name>/`.
2. Provide:
   - `task.yaml`: Task metadata, timeouts, resource limits, and scoring weights.
   - `prompt.md`: Instructions presented to the agent.
   - `Dockerfile`: Pinned dependencies and base image.
   - `app/`: Target application source code.
   - `fixtures/broken.env`: Deterministic fault fixture.
   - `fixtures/repaired.env`: Ground-truth reference fix.
   - `tests/`: Independent test modules (`test_configuration.py`, `test_service_health.py`, `test_behavior.py`, `test_regression.py`).
3. Validate task integrity:
   ```bash
   agentbench validate <task-name>
   ```

---

## 7. How to Implement an Agent Adapter

Subclass `AgentAdapter` and implement `solve()`:

```python
from agentbench.agent_adapter import AgentAdapter, AgentResult, TaskEnvironment
from agentbench.models import BenchmarkTask


class MyLLMAgent(AgentAdapter):
    name = "my-llm-agent"

    def solve(self, task: BenchmarkTask, environment: TaskEnvironment) -> AgentResult:
        files = environment.list_files()
        config = environment.read_file(".env")

        # Query your LLM model with task.prompt_content
        # Apply repair using environment.write_file() or environment.apply_patch()
        environment.write_file(".env", 'BENCH_CATALOG_ITEMS=["alpha", "beta"]')

        return AgentResult(
            success=True,
            duration_seconds=3.2,
            tool_calls=environment.tool_call_count,
            summary="Repaired invalid environment variable",
            termination_reason="completed",
        )
```

---

## 8. Example Benchmark Report

```json
{
  "schema_version": "1.0",
  "run_id": "sample-run-001",
  "task_id": "config-recovery-001",
  "task_version": "1.0.0",
  "status": "passed",
  "score": 100.0,
  "duration_seconds": 2.63,
  "agent": {
    "name": "scripted-baseline",
    "tool_calls": 3,
    "termination_reason": "completed",
    "summary": "Diagnosed invalid configuration in .env and restored valid catalog items."
  },
  "criteria": {
    "configuration": {"weight": 30.0, "passed": true, "score": 30.0},
    "startup": {"weight": 20.0, "passed": true, "score": 20.0},
    "behavior": {"weight": 30.0, "passed": true, "score": 30.0},
    "regression": {"weight": 20.0, "passed": true, "score": 20.0}
  },
  "artifacts": [
    "results/sample-run-001_artifacts/agent.log",
    "results/sample-run-001_artifacts/evaluator.log",
    "results/sample-run-001_artifacts/container.log",
    "results/sample-run-001_artifacts/patch.diff"
  ]
}
```

---

## 9. Benchmark Suite

| Task ID | Category | Difficulty | Measured Capability | Status |
| :--- | :--- | :--- | :--- | :--- |
| `config-recovery-001` | Configuration Recovery | Medium | Diagnose setting error and restore behavior | **Included (v0.1.0)** |
| `contract-repair-001` | API Contract Repair | Medium | Repair request/response schema violation | **Included (v0.2.0)** |
| `multi-service-cache-001` | Multi-Service Distributed Cache | Hard | Diagnose connection pool exhaustion & port error | **Included (v0.3.0)** |
| `dependency-conflict-001` | Package Compatibility | Medium | Resolve conflicting pinned package versions | Roadmap |
| `database-migration-001` | Schema Migration | Hard | Repair schema migration issue while preserving data | Roadmap |

---

## 10. License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
