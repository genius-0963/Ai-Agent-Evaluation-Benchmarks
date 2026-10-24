import json
from pathlib import Path

from agentbench.models import (
    AgentReportInfo,
    BenchmarkReport,
    CriterionDetail,
    RunStatus,
)
from agentbench.reporting import (
    format_terminal_summary,
    load_report,
    save_report,
    validate_report_schema,
)


def test_schema_validation_on_sample_report():
    sample_file = Path("examples/sample_report.json")
    assert sample_file.is_file()
    with open(sample_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    validate_report_schema(data)


def test_save_and_load_report(tmp_path: Path):
    report = BenchmarkReport(
        schema_version="1.0",
        run_id="run-unit-001",
        task_id="config-recovery-001",
        task_version="1.0.0",
        status=RunStatus.PASSED,
        score=100.0,
        duration_seconds=5.2,
        agent=AgentReportInfo(
            name="unit-tester", tool_calls=1, termination_reason="completed"
        ),
        criteria={"configuration": CriterionDetail(weight=30, passed=True, score=30)},
        artifacts=[],
    )

    out_file = save_report(report, tmp_path)
    assert out_file.is_file()

    loaded = load_report(out_file)
    assert loaded.run_id == "run-unit-001"
    assert loaded.score == 100.0


def test_format_terminal_summary():
    report = BenchmarkReport(
        schema_version="1.0",
        run_id="run-unit-002",
        task_id="config-recovery-001",
        status=RunStatus.PASSED,
        score=100.0,
        duration_seconds=3.0,
        agent=AgentReportInfo(
            name="scripted", tool_calls=2, termination_reason="completed"
        ),
        criteria={"configuration": CriterionDetail(weight=30, passed=True, score=30)},
    )
    summary = format_terminal_summary(report)
    assert "BENCHMARK RUN SUMMARY: run-unit-002" in summary
    assert "PASSED [✓]" in summary
