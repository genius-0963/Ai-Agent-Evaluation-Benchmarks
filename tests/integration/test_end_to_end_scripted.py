from agentbench.models import RunStatus
from agentbench.runner import BenchmarkRunner


def test_end_to_end_scripted_agent():
    runner = BenchmarkRunner()
    report = runner.run("config-recovery-001", agent_name="scripted")

    assert report.status == RunStatus.PASSED
    assert report.score == 100.0
    assert report.agent.name == "scripted-baseline"
    assert report.criteria["configuration"].passed is True
    assert report.criteria["startup"].passed is True
    assert report.criteria["behavior"].passed is True
    assert report.criteria["regression"].passed is True
    assert len(report.artifacts) >= 2
