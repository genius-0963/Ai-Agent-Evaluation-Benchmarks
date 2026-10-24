"""Domain models and schemas for agentbench."""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class RunStatus(str, Enum):
    """Execution status for a benchmark run."""

    PASSED = "passed"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    EVALUATOR_ERROR = "evaluator_error"


class FailureClassification(str, Enum):
    """Fine-grained failure taxonomy for observability and error analysis."""

    NONE = "none"
    DIAGNOSIS_FAILURE = "diagnosis_failure"
    PATCH_SYNTAX_ERROR = "patch_syntax_error"
    FUNCTIONAL_FAILURE = "functional_failure"
    REGRESSION_VIOLATION = "regression_violation"
    SECURITY_VIOLATION = "security_violation"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


class SecurityConfig(BaseModel):
    """Hardened security and anti-tamper specifications."""

    hidden_tests: bool = True
    protect_evaluator: bool = True
    randomized_inputs: bool = True
    detect_filesystem_tampering: bool = True
    read_only_rootfs: bool = False


class TaskEnvironmentConfig(BaseModel):
    """Container environment specifications."""

    dockerfile: str = "Dockerfile"
    image: str | None = None
    working_directory: str = "/workspace"
    startup_timeout_seconds: int = Field(default=30, ge=1)
    execution_timeout_seconds: int = Field(default=120, ge=1)
    memory_limit: str = "512m"
    memory_mb: int = 512
    cpus: float = Field(default=1.0, gt=0)
    cpu_cores: float = Field(default=1.0, gt=0)
    network_enabled: bool = False
    network: str = "disabled"
    read_only_rootfs: bool = False


class FaultConfig(BaseModel):
    """Controlled fault specification."""

    type: str
    target_file: str | None = None
    fixture_file: str | None = None
    repaired_fixture_file: str | None = None
    description: str | None = None
    reset_procedure: str | None = None


class AgentConfig(BaseModel):
    """Limits and guidelines for the agent."""

    prompt_file: str = "prompt.md"
    tools: list[str] = Field(
        default_factory=lambda: ["read_file", "write_file", "list_files", "run_command"]
    )
    max_runtime_seconds: int = Field(default=300, ge=1)
    max_tool_calls: int = Field(default=40, ge=1)
    temperature: float = 0.0
    seed: int | None = 42


class EvaluationConfig(BaseModel):
    """Independent evaluation specification."""

    tests_directory: str = "tests"
    pass_threshold: float = Field(default=80.0, ge=0.0, le=100.0)


class ScoringCriteria(BaseModel):
    """Weighted criteria breakdown (weights must sum to 100)."""

    configuration: float = 30.0
    startup: float = 20.0
    behavior: float = 30.0
    regression: float = 20.0

    @model_validator(mode="after")
    def validate_total_weight(self) -> "ScoringCriteria":
        total = self.configuration + self.startup + self.behavior + self.regression
        if round(total, 2) != 100.0:
            raise ValueError(f"Scoring weights must sum to 100, got {total}")
        return self


class BenchmarkTask(BaseModel):
    """Complete specification of a benchmark task manifest."""

    id: str
    name: str
    version: str = "1.0.0"
    category: str = "software_repair"
    difficulty: str = "medium"
    description: str
    environment: TaskEnvironmentConfig = Field(default_factory=TaskEnvironmentConfig)
    fault: FaultConfig
    agent: AgentConfig = Field(default_factory=AgentConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    scoring: ScoringCriteria = Field(default_factory=ScoringCriteria)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    artifacts: list[str] = Field(
        default_factory=lambda: [
            "agent.log",
            "patch.diff",
            "evaluator.log",
            "container.log",
            "report.json",
        ]
    )

    # Runtime metadata not loaded from task.yaml
    task_dir: Path | None = None
    prompt_content: str = ""


# Reporting Models
class CriterionDetail(BaseModel):
    """Evaluation result for an individual scoring criterion."""

    weight: float
    passed: bool
    score: float = 0.0
    details: str | None = None


class AgentReportInfo(BaseModel):
    """Agent runtime metrics in the benchmark report."""

    name: str
    tool_calls: int
    termination_reason: str
    summary: str = ""
    model_version: str | None = None
    temperature: float = 0.0
    seed: int | None = None


class BenchmarkReport(BaseModel):
    """Standardized benchmark execution report."""

    schema_version: str = "1.0"
    run_id: str
    task_id: str
    task_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: RunStatus
    failure_classification: FailureClassification = FailureClassification.NONE
    score: float
    duration_seconds: float
    agent: AgentReportInfo
    criteria: dict[str, CriterionDetail]
    artifacts: list[str] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    # Research & observability metrics
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    inference_latency_seconds: float = 0.0
    execution_latency_seconds: float = 0.0
    security_violations: list[str] = Field(default_factory=list)
    regression_detected: bool = False
