import docker

from agentbench.docker_manager import DockerManager
from agentbench.models import RunStatus
from agentbench.runner import BenchmarkRunner
from agentbench.task_loader import load_task


def test_docker_container_lifecycle_and_cleanup():
    task = load_task("config-recovery-001")
    dm = DockerManager()

    # Build image
    image_tag = dm.build_image(task)
    assert image_tag == f"agentbench-{task.id}:{task.version}"

    # Create and inspect container
    container = dm.create_container(
        task=task,
        run_id="lifecycle-test",
        command_override=["tail", "-f", "/dev/null"],
    )

    try:
        assert dm.wait_until_ready(container, timeout_seconds=10) is True

        # Test command execution
        exit_code, stdout, stderr = dm.exec_command(
            container, ["echo", "sandbox-active"]
        )
        assert exit_code == 0
        assert "sandbox-active" in stdout

        # Collect logs
        stdout_log, stderr_log = dm.collect_logs(container)
        assert isinstance(stdout_log, str)
    finally:
        dm.cleanup(container)

    # Verify container removed
    client = docker.from_env()
    remaining = client.containers.list(all=True, filters={"name": "lifecycle-test"})
    assert len(remaining) == 0


def test_docker_runner_end_to_end():
    runner = BenchmarkRunner(use_docker=True)
    report = runner.run("config-recovery-001", agent_name="scripted")

    assert report.status == RunStatus.PASSED
    assert report.score == 100.0
    assert report.environment.get("docker_enabled") is True
