from agentbench.models import RunStatus
from agentbench.runner import BenchmarkRunner


def test_end_to_end_noop_agent_fails():
    runner = BenchmarkRunner()
    report = runner.run("config-recovery-001", agent_name="noop")

    assert report.status == RunStatus.FAILED
    assert report.score == 0.0
    assert report.agent.name == "no-op"
    assert report.criteria["configuration"].passed is False
    assert report.criteria["startup"].passed is False
    assert report.criteria["behavior"].passed is False
    assert report.criteria["regression"].passed is False
