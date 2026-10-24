"""Resource lifecycle cleanup manager for temporary containers and host directories."""

import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger("agentbench.cleanup")


class CleanupManager:
    """Tracks active resources during execution and guarantees cleanup upon termination."""

    def __init__(self) -> None:
        self.containers: list[Any] = []
        self.temp_directories: list[Path] = []

    def register_container(self, container: Any) -> None:
        """Register a container to be stopped and removed on cleanup."""
        self.containers.append(container)

    def register_directory(self, path: Path) -> None:
        """Register a temporary directory to be deleted on cleanup."""
        self.temp_directories.append(path)

    def cleanup(self) -> None:
        """Execute complete cleanup of registered containers and directories."""
        for container in self.containers:
            try:
                container.stop(timeout=2)
            except Exception:
                pass
            try:
                container.remove(force=True, v=True)
            except Exception:
                pass

        self.containers.clear()

        for temp_dir in self.temp_directories:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to remove temporary directory {temp_dir}: {e}")

        self.temp_directories.clear()
