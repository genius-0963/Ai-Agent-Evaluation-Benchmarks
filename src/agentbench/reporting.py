"""Report generation, schema validation, serialization, and presentation."""

import json
from pathlib import Path
from typing import Any

import jsonschema

from agentbench.models import BenchmarkReport, RunStatus

REPORT_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "BenchmarkReport",
    "type": "object",
    "required": [
        "schema_version",
        "run_id",
        "task_id",
        "status",
        "score",
        "duration_seconds",
        "agent",
        "criteria",
        "artifacts",
    ],
    "properties": {
        "schema_version": {"type": "string"},
        "run_id": {"type": "string"},
        "task_id": {"type": "string"},
        "task_version": {"type": "string"},
        "timestamp": {"type": "string"},
        "status": {
            "type": "string",
            "enum": [
                "passed",
                "partial",
                "failed",
                "timeout",
                "infrastructure_error",
                "evaluator_error",
            ],
        },
        "failure_classification": {"type": "string"},
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "duration_seconds": {"type": "number", "minimum": 0},
        "agent": {
            "type": "object",
            "required": ["name", "tool_calls", "termination_reason"],
            "properties": {
                "name": {"type": "string"},
                "tool_calls": {"type": "integer", "minimum": 0},
                "termination_reason": {"type": "string"},
                "summary": {"type": "string"},
                "model_version": {"type": ["string", "null"]},
                "temperature": {"type": "number"},
                "seed": {"type": ["integer", "null"]},
            },
        },
        "criteria": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "required": ["weight", "passed"],
                "properties": {
                    "weight": {"type": "number"},
                    "passed": {"type": "boolean"},
                    "score": {"type": "number"},
                    "details": {"type": ["string", "null"]},
                },
            },
        },
        "artifacts": {
            "type": "array",
            "items": {"type": "string"},
        },
        "environment": {"type": "object"},
        "error": {"type": ["string", "null"]},
        "cost_usd": {"type": "number"},
        "input_tokens": {"type": "integer"},
        "output_tokens": {"type": "integer"},
        "total_tokens": {"type": "integer"},
        "inference_latency_seconds": {"type": "number"},
        "execution_latency_seconds": {"type": "number"},
        "security_violations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "regression_detected": {"type": "boolean"},
    },
}


def validate_report_schema(data: dict[str, Any]) -> None:
    """Validate raw report dictionary against strict JSON Schema."""
    jsonschema.validate(instance=data, schema=REPORT_JSON_SCHEMA)


def save_report(report: BenchmarkReport, results_dir: Path | str = "results") -> Path:
    """Persist report to JSON and Markdown files."""
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / f"{report.run_id}.json"

    raw_dict = report.model_dump(mode="json")
    validate_report_schema(raw_dict)

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(raw_dict, f, indent=2)

    # Also export Markdown summary report
    md_file = out_dir / f"{report.run_id}.md"
    md_file.write_text(generate_markdown_report(report), encoding="utf-8")

    return report_file


def load_report(report_path: Path | str) -> BenchmarkReport:
    """Load and validate an existing benchmark report JSON file."""
    path = Path(report_path)
    if not path.is_file():
        raise FileNotFoundError(f"Report file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    validate_report_schema(data)
    return BenchmarkReport.model_validate(data)


def generate_markdown_report(report: BenchmarkReport) -> str:
    """Generate publication-ready Markdown benchmark evaluation report."""
    icon = (
        "PASSED (100%)"
        if report.status == RunStatus.PASSED
        else f"{report.status.value.upper()}"
    )
    lines = [
        f"# Benchmark Run Report: `{report.run_id}`",
        "",
        "## Executive Summary",
        f"- **Task**: `{report.task_id}` (v{report.task_version})",
        f"- **Status**: **{icon}**",
        f"- **Score**: `{report.score:.1f} / 100.0`",
        f"- **Failure Taxonomy**: `{report.failure_classification.value}`",
        f"- **Duration**: `{report.duration_seconds:.2f}s` (Inference: `{report.inference_latency_seconds:.2f}s`, Execution: `{report.execution_latency_seconds:.2f}s`)",
        "",
        "## Agent Profile & Efficiency",
        f"- **Agent**: `{report.agent.name}`",
        f"- **Tool Calls**: `{report.agent.tool_calls}`",
        f"- **Tokens**: `{report.total_tokens}` (Input: `{report.input_tokens}`, Output: `{report.output_tokens}`)",
        f"- **Estimated Cost**: `\\${report.cost_usd:.4f}`",
        f"- **Termination Reason**: `{report.agent.termination_reason}`",
        f"- **Summary**: {report.agent.summary}",
        "",
        "## Criteria Evaluation Breakdown",
        "| Criterion | Weight | Result | Score Earned | Details |",
        "| :--- | :--- | :---: | :---: | :--- |",
    ]
    for crit, det in report.criteria.items():
        res = "PASS" if det.passed else "FAIL"
        lines.append(
            f"| **{crit.capitalize()}** | {det.weight:.0f} | {res} | {det.score:.1f} | {det.details or ''} |"
        )

    if report.security_violations:
        lines.extend(
            [
                "",
                "## Security & Anti-Tamper Violations",
                "> [!CAUTION]",
                "> The following security or sandbox boundary violations were detected:",
            ]
        )
        for v in report.security_violations:
            lines.append(f"- `{v}`")

    if report.regression_detected:
        lines.extend(
            [
                "",
                "## Regression Notice",
                "> [!WARNING]",
                "> Regression detected: Previously passing baseline endpoints were broken by this patch.",
            ]
        )

    lines.extend(
        [
            "",
            "## Preserved Artifacts",
        ]
    )
    for a in report.artifacts:
        lines.append(f"- `{a}`")

    return "\n".join(lines)


def format_terminal_summary(report: BenchmarkReport) -> str:
    """Render a clean ASCII table summary for CLI presentation."""
    status_icon = "✓" if report.status == RunStatus.PASSED else "✗"
    lines = [
        "=" * 65,
        f"BENCHMARK RUN SUMMARY: {report.run_id}",
        "=" * 65,
        f"Task ID:          {report.task_id} (v{report.task_version})",
        f"Status:           {report.status.value.upper()} [{status_icon}]",
        f"Failure Type:     {report.failure_classification.value.upper()}",
        f"Final Score:      {report.score:.1f} / 100.0",
        f"Total Duration:   {report.duration_seconds:.2f}s (Exec: {report.execution_latency_seconds:.2f}s, Inf: {report.inference_latency_seconds:.2f}s)",
        "-" * 65,
        f"Agent:            {report.agent.name}",
        f"Tool Calls:       {report.agent.tool_calls}",
        f"Tokens / Cost:    {report.total_tokens} tokens / \\${report.cost_usd:.4f}",
        f"Agent Summary:    {report.agent.summary}",
        "-" * 65,
        "CRITERIA BREAKDOWN:",
    ]
    for crit, det in report.criteria.items():
        box = "[PASS]" if det.passed else "[FAIL]"
        lines.append(
            f"  • {crit:<15} {box:<6} {det.score:>4.1f} / {det.weight:<4.1f} pts"
        )

    if report.security_violations:
        lines.append("-" * 65)
        lines.append("SECURITY VIOLATIONS DETECTED:")
        for v in report.security_violations:
            lines.append(f"  [VIOLATION] {v}")

    if report.artifacts:
        lines.append("-" * 65)
        lines.append("ARTIFACTS:")
        for art in report.artifacts:
            lines.append(f"  • {art}")

    if report.error:
        lines.append("-" * 65)
        lines.append(f"ERROR: {report.error}")

    lines.append("=" * 65)
    return "\n".join(lines)
