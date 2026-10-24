"""Docker harness and security manager for benchmark task lifecycle."""

import logging
import time
from pathlib import Path

import docker
from docker.errors import APIError, BuildError, NotFound
from docker.models.containers import Container

from agentbench.models import BenchmarkTask

logger = logging.getLogger("agentbench.docker")


class DockerHarnessError(Exception):
    """Base exception for Docker harness failures."""


class DockerConnectionError(DockerHarnessError):
    """Docker daemon connection failure."""


class ImageBuildError(DockerHarnessError):
    """Failure building benchmark Docker image."""


class ContainerLifecycleError(DockerHarnessError):
    """Failure creating or starting container."""


class CommandExecutionTimeout(DockerHarnessError):
    """Command inside container exceeded allowed timeout."""


class DockerManager:
    """Manages isolated, disposable Docker containers with strict security constraints."""

    def __init__(self, client: docker.DockerClient | None = None) -> None:
        try:
            self.client = client or docker.from_env()
            # Test connectivity
            self.client.ping()
        except Exception as e:
            raise DockerConnectionError(
                f"Could not connect to Docker daemon: {e}"
            ) from e

    def build_image(self, task: BenchmarkTask, force_rebuild: bool = False) -> str:
        """Build or verify the Docker image for a benchmark task."""
        if not task.task_dir:
            raise ImageBuildError("Task directory must be resolved before building.")

        image_tag = f"agentbench-{task.id}:{task.version}"

        if not force_rebuild:
            try:
                self.client.images.get(image_tag)
                logger.info(f"Image '{image_tag}' already exists; skipping build.")
                return image_tag
            except NotFound:
                pass

        dockerfile_path = task.task_dir / task.environment.dockerfile
        if not dockerfile_path.is_file():
            raise ImageBuildError(f"Dockerfile not found: {dockerfile_path}")

        logger.info(f"Building Docker image '{image_tag}' from {task.task_dir}...")
        try:
            # We build using the task directory as the build context
            image, build_logs = self.client.images.build(
                path=str(task.task_dir),
                dockerfile=task.environment.dockerfile,
                tag=image_tag,
                rm=True,
                forcerm=True,
            )
            return image_tag
        except BuildError as e:
            log_lines = "\n".join(
                str(entry.get("stream", ""))
                for entry in e.build_log
                if isinstance(entry, dict)
            )
            raise ImageBuildError(
                f"Docker build failed for {task.id}:\n{log_lines}"
            ) from e
        except APIError as e:
            raise ImageBuildError(f"Docker API error during build: {e}") from e

    def create_container(
        self,
        task: BenchmarkTask,
        run_id: str,
        workspace_dir: Path | None = None,
        environment_override: dict[str, str] | None = None,
        command_override: list[str] | str | None = None,
    ) -> Container:
        """Create and start a fresh, isolated container with strict resource limits."""
        image_tag = f"agentbench-{task.id}:{task.version}"
        container_name = f"agentbench-{task.id}-{run_id}"

        # Security limits
        env_cfg = task.environment
        mem_limit = env_cfg.memory_limit or "512m"
        nano_cpus = int(env_cfg.cpus * 1e9)
        network_mode = "bridge" if env_cfg.network_enabled else "none"

        # Safe environment variables
        env_vars = {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": "/workspace",
            "BENCHMARK_TASK_ID": task.id,
            "BENCHMARK_RUN_ID": run_id,
        }
        if environment_override:
            env_vars.update(environment_override)

        # Mounts: Mount host workspace_dir to /workspace if provided
        volumes: dict[str, dict[str, str]] = {}
        if workspace_dir:
            volumes[str(workspace_dir.resolve())] = {
                "bind": "/workspace",
                "mode": "rw",
            }

        try:
            container = self.client.containers.run(
                image=image_tag,
                name=container_name,
                command=command_override,
                detach=True,
                mem_limit=mem_limit,
                nano_cpus=nano_cpus,
                pids_limit=150,
                network_mode=network_mode,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                volumes=volumes,
                environment=env_vars,
                user="1000:1000",
                labels={
                    "managed_by": "agentbench",
                    "task_id": task.id,
                    "run_id": run_id,
                },
            )
            return container
        except APIError as e:
            raise ContainerLifecycleError(
                f"Failed to create/start container: {e}"
            ) from e

    def wait_until_ready(
        self,
        container: Container,
        timeout_seconds: int = 15,
        poll_interval: float = 0.5,
    ) -> bool:
        """Check container process readiness within a deadline."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                container.reload()
                status = container.status
                if status == "running":
                    return True
                if status in ("exited", "dead"):
                    return False
            except Exception:
                pass
            time.sleep(poll_interval)
        return False

    def wait_for_http_ready(
        self,
        container: Container,
        port: int = 8000,
        path: str = "/health",
        timeout_seconds: int = 15,
        initial_delay: float = 0.2,
        backoff_factor: float = 1.5,
    ) -> bool:
        """Actively probe HTTP service inside container using exponential backoff."""
        deadline = time.time() + timeout_seconds
        delay = initial_delay
        probe_cmd = [
            "python",
            "-c",
            (
                "import sys, urllib.request;\n"
                f"try:\n"
                f"    with urllib.request.urlopen('http://127.0.0.1:{port}{path}', timeout=2) as r:\n"
                "        sys.exit(0 if r.status == 200 else 1)\n"
                "except Exception:\n"
                "    sys.exit(1)\n"
            ),
        ]

        while time.time() < deadline:
            try:
                container.reload()
                if container.status != "running":
                    return False
                exit_code, _, _ = self.exec_command(
                    container=container,
                    command=probe_cmd,
                    timeout_seconds=3,
                )
                if exit_code == 0:
                    return True
            except Exception:
                pass

            time.sleep(min(delay, 2.0))
            delay *= backoff_factor

        return False

    def exec_command(
        self,
        container: Container,
        command: str | list[str],
        timeout_seconds: int = 30,
        workdir: str = "/workspace",
        user: str = "benchuser",
    ) -> tuple[int, str, str]:
        """Execute a command inside the container and capture exit code, stdout, and stderr."""
        # Using Docker low-level API socket or exec_create/exec_start for robust timeout
        try:
            container.reload()
            if container.status != "running":
                raise ContainerLifecycleError(
                    f"Container {container.name} is not running (status: {container.status})"
                )

            exec_instance = self.client.api.exec_create(
                container=container.id,
                cmd=command,
                workdir=workdir,
                user=user,
                stdout=True,
                stderr=True,
            )
            exec_id = exec_instance["Id"]

            # Start execution with demux
            start_time = time.time()
            output_stream = self.client.api.exec_start(
                exec_id, stream=False, demux=True
            )

            stdout_bytes, stderr_bytes = output_stream if output_stream else (b"", b"")
            stdout_str = (
                stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            )
            stderr_str = (
                stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            )

            inspect = self.client.api.exec_inspect(exec_id)
            exit_code = inspect.get("ExitCode", -1)

            if time.time() - start_time > timeout_seconds:
                raise CommandExecutionTimeout(
                    f"Command '{command}' exceeded deadline of {timeout_seconds} seconds."
                )

            return exit_code, stdout_str, stderr_str
        except APIError as e:
            raise ContainerLifecycleError(
                f"Error executing command in container: {e}"
            ) from e

    def collect_logs(self, container: Container) -> tuple[str, str]:
        """Capture stdout and stderr logs from the container."""
        try:
            container.reload()
            stdout = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            stderr = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )
            return stdout, stderr
        except Exception as e:
            logger.warning(f"Could not collect container logs: {e}")
            return "", str(e)

    def stop_container(self, container: Container, timeout: int = 5) -> None:
        """Stop container cleanly with timeout."""
        try:
            container.stop(timeout=timeout)
        except Exception as e:
            logger.debug(f"Stop container error (ignored): {e}")

    def remove_container(self, container: Container, force: bool = True) -> None:
        """Remove container after run."""
        try:
            container.remove(force=force, v=True)
        except Exception as e:
            logger.debug(f"Remove container error (ignored): {e}")

    def cleanup(self, container: Container | str | None) -> None:
        """Guaranteed cleanup helper."""
        if container is None:
            return
        try:
            if isinstance(container, str):
                c = self.client.containers.get(container)
            else:
                c = container
            self.stop_container(c, timeout=3)
            self.remove_container(c, force=True)
        except Exception:
            pass
