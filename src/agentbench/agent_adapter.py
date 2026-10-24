"""Agent adapter interfaces, environment tool execution, and concrete agent implementations."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from agentbench.models import BenchmarkTask
from agentbench.workspace import Workspace

logger = logging.getLogger("agentbench.adapter")


@dataclass
class AgentResult:
    """Outcome of an agent's attempt to repair a task."""

    success: bool
    duration_seconds: float
    tool_calls: int
    summary: str
    error: str | None = None
    patch_applied: str | None = None
    termination_reason: str = (
        "completed"  # "completed", "timeout", "budget_exceeded", "error"
    )
    history: list[dict[str, Any]] = field(default_factory=list)


class ToolBudgetExceeded(Exception):
    """Raised when the agent exceeds the allowed number of tool calls."""


class RuntimeBudgetExceeded(Exception):
    """Raised when the agent exceeds the allowed wall-clock runtime."""


class TaskEnvironment:
    """Restricted tool interface provided to the agent during solve loop."""

    def __init__(self, workspace: Workspace, task: BenchmarkTask) -> None:
        self.workspace = workspace
        self.task = task
        self.max_tool_calls = task.agent.max_tool_calls
        self.max_runtime_seconds = task.agent.max_runtime_seconds
        self.start_time = time.time()
        self.tool_call_count = 0
        self.history: list[dict[str, Any]] = []

    def _check_budgets(self, tool_name: str) -> None:
        elapsed = time.time() - self.start_time
        if elapsed > self.max_runtime_seconds:
            raise RuntimeBudgetExceeded(
                f"Agent runtime budget of {self.max_runtime_seconds}s exceeded (elapsed: {elapsed:.2f}s)"
            )
        if self.tool_call_count >= self.max_tool_calls:
            raise ToolBudgetExceeded(
                f"Agent tool budget of {self.max_tool_calls} calls exceeded"
            )
        self.tool_call_count += 1

    def read_file(self, path: str) -> str:
        """Read content of a file in the workspace."""
        self._check_budgets("read_file")
        try:
            content = self.workspace.read_file(path)
            self.history.append(
                {"tool": "read_file", "path": path, "status": "success"}
            )
            return content
        except Exception as e:
            self.history.append(
                {"tool": "read_file", "path": path, "status": "error", "error": str(e)}
            )
            raise

    def list_files(self, path: str = ".") -> list[str]:
        """List files in the workspace directory."""
        self._check_budgets("list_files")
        try:
            files = self.workspace.list_files(path)
            self.history.append(
                {
                    "tool": "list_files",
                    "path": path,
                    "status": "success",
                    "count": len(files),
                }
            )
            return files
        except Exception as e:
            self.history.append(
                {"tool": "list_files", "path": path, "status": "error", "error": str(e)}
            )
            raise

    def search_text(self, query: str, path: str = ".") -> list[dict[str, Any]]:
        """Search for text in workspace files."""
        self._check_budgets("search_text")
        try:
            results = self.workspace.search_text(query, path)
            self.history.append(
                {
                    "tool": "search_text",
                    "query": query,
                    "status": "success",
                    "matches": len(results),
                }
            )
            return results
        except Exception as e:
            self.history.append(
                {
                    "tool": "search_text",
                    "query": query,
                    "status": "error",
                    "error": str(e),
                }
            )
            raise

    def write_file(self, path: str, content: str) -> None:
        """Write content to a file in the workspace."""
        self._check_budgets("write_file")
        try:
            self.workspace.write_file(path, content)
            self.history.append(
                {
                    "tool": "write_file",
                    "path": path,
                    "status": "success",
                    "bytes": len(content),
                }
            )
        except Exception as e:
            self.history.append(
                {"tool": "write_file", "path": path, "status": "error", "error": str(e)}
            )
            raise

    def apply_patch(self, patch: str) -> bool:
        """Apply a patch to files in the workspace."""
        self._check_budgets("apply_patch")
        try:
            res = self.workspace.apply_patch(patch)
            self.history.append(
                {"tool": "apply_patch", "status": "success" if res else "failed"}
            )
            return res
        except Exception as e:
            self.history.append(
                {"tool": "apply_patch", "status": "error", "error": str(e)}
            )
            raise

    def run_allowed_command(self, command: str) -> tuple[int, str, str]:
        """Run a command from the allowed security list."""
        self._check_budgets("run_allowed_command")
        try:
            code, stdout, stderr = self.workspace.run_allowed_command(command)
            self.history.append(
                {
                    "tool": "run_allowed_command",
                    "command": command,
                    "exit_code": code,
                }
            )
            return code, stdout, stderr
        except Exception as e:
            self.history.append(
                {"tool": "run_allowed_command", "command": command, "error": str(e)}
            )
            raise


class AgentAdapter(ABC):
    """Abstract base class for all benchmark agent adapters."""

    name: str = "base-agent"

    @abstractmethod
    def solve(self, task: BenchmarkTask, environment: TaskEnvironment) -> AgentResult:
        """Attempt the task within the supplied limits."""
        raise NotImplementedError


class ScriptedAgent(AgentAdapter):
    """Scripted baseline agent applying a known repair to validate the evaluation pipeline."""

    name: str = "scripted-baseline"

    def solve(self, task: BenchmarkTask, environment: TaskEnvironment) -> AgentResult:
        start_time = time.time()
        try:
            # 1. Inspect workspace
            files = environment.list_files()

            # 2. Check configuration file
            target_file = task.fault.target_file or ".env"
            if target_file in files or f"./{target_file}" in files:
                _ = environment.read_file(target_file)

            # 3. Read repaired fixture if available, or write standard repair
            repaired_content = None
            if task.fault.repaired_fixture_file and task.task_dir:
                fix_path = task.task_dir / task.fault.repaired_fixture_file
                if fix_path.is_file():
                    repaired_content = fix_path.read_text(encoding="utf-8")

            if not repaired_content:
                repaired_content = (
                    'BENCH_APP_NAME="Benchmark Catalog"\n'
                    'BENCH_CATALOG_ITEMS=["alpha", "beta"]\n'
                )

            # 4. Apply repair
            environment.write_file(target_file, repaired_content)

            duration = round(time.time() - start_time, 2)
            return AgentResult(
                success=True,
                duration_seconds=duration,
                tool_calls=environment.tool_call_count,
                summary=f"Diagnosed invalid configuration in {target_file} and restored valid catalog items.",
                patch_applied=repaired_content,
                termination_reason="completed",
                history=environment.history,
            )
        except (ToolBudgetExceeded, RuntimeBudgetExceeded) as e:
            return AgentResult(
                success=False,
                duration_seconds=round(time.time() - start_time, 2),
                tool_calls=environment.tool_call_count,
                summary="Budget exceeded during repair attempt.",
                error=str(e),
                termination_reason="budget_exceeded",
                history=environment.history,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                duration_seconds=round(time.time() - start_time, 2),
                tool_calls=environment.tool_call_count,
                summary="Scripted agent encountered unexpected error.",
                error=str(e),
                termination_reason="error",
                history=environment.history,
            )


class NoOpAgent(AgentAdapter):
    """No-op agent that inspects files but makes no modifications. Must fail functional evaluation."""

    name: str = "no-op"

    def solve(self, task: BenchmarkTask, environment: TaskEnvironment) -> AgentResult:
        start_time = time.time()
        try:
            # Observes files passively
            environment.list_files()
            target_file = task.fault.target_file or ".env"
            try:
                environment.read_file(target_file)
            except Exception:
                pass

            duration = round(time.time() - start_time, 2)
            return AgentResult(
                success=False,
                duration_seconds=duration,
                tool_calls=environment.tool_call_count,
                summary="No-op agent observed the workspace and made no changes.",
                termination_reason="completed",
                history=environment.history,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                duration_seconds=round(time.time() - start_time, 2),
                tool_calls=environment.tool_call_count,
                summary="No-op agent failed.",
                error=str(e),
                termination_reason="error",
                history=environment.history,
            )


class LLMAgent(AgentAdapter):
    """LLM-backed agent using prompt reasoning and tool calling."""

    name: str = "llm-agent"

    def __init__(
        self, model_name: str = "mock-reasoner", api_key: str | None = None
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key

    def solve(self, task: BenchmarkTask, environment: TaskEnvironment) -> AgentResult:
        start_time = time.time()
        try:
            # 1. Step: list files
            files = environment.list_files()

            # 2. Step: inspect target file
            target_file = task.fault.target_file or ".env"
            if target_file in files:
                content = environment.read_file(target_file)
            else:
                content = ""

            # 3. Step: analyze and repair
            if "INVALID" in content or "ERROR" in content:
                # Heuristic repair simulation when no live external API is configured
                fixed_content = (
                    'BENCH_APP_NAME="Benchmark Catalog"\n'
                    'BENCH_CATALOG_ITEMS=["alpha", "beta"]\n'
                )
                environment.write_file(target_file, fixed_content)
                summary = f"Identified malformed config in {target_file}. Corrected JSON format for BENCH_CATALOG_ITEMS."
                success = True
            else:
                summary = "Did not detect known error pattern."
                success = False

            duration = round(time.time() - start_time, 2)
            return AgentResult(
                success=success,
                duration_seconds=duration,
                tool_calls=environment.tool_call_count,
                summary=summary,
                termination_reason="completed",
                history=environment.history,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                duration_seconds=round(time.time() - start_time, 2),
                tool_calls=environment.tool_call_count,
                summary="LLM agent encountered an error.",
                error=str(e),
                termination_reason="error",
                history=environment.history,
            )


def get_agent(agent_name: str, **kwargs: Any) -> AgentAdapter:
    """Agent factory to resolve agent instances by name."""
    clean_name = agent_name.lower().strip()
    if clean_name in ("scripted", "scripted-baseline", "baseline"):
        return ScriptedAgent()
    elif clean_name in ("noop", "no-op"):
        return NoOpAgent()
    elif clean_name in ("llm", "llm-agent", "model") or any(
        m in clean_name for m in ("gpt", "claude", "gemini", "ollama", "mistral")
    ):
        from agentbench.adapters.llm_engine import LLMEngineAgent

        return LLMEngineAgent(model_name=agent_name, **kwargs)
    else:
        raise ValueError(
            f"Unknown agent adapter: '{agent_name}'. Available: scripted, no-op, llm, gpt-4o, claude-3-5-sonnet, gemini"
        )
