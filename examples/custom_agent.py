"""Example of implementing a custom AI agent adapter for agentbench."""

import time

from agentbench.agent_adapter import AgentAdapter, AgentResult, TaskEnvironment
from agentbench.models import BenchmarkTask


class CustomDiagnosticAgent(AgentAdapter):
    """An example custom agent that inspects files and applies smart fixes."""

    name = "custom-diagnostic-agent"

    def solve(self, task: BenchmarkTask, environment: TaskEnvironment) -> AgentResult:
        start_time = time.time()

        # Step 1: Discover workspace structure
        _ = environment.list_files()

        # Step 2: Read prompt to understand task
        _ = task.prompt_content

        # Step 3: Inspect suspect configuration file
        target_file = task.fault.target_file or ".env"
        current_config = environment.read_file(target_file)

        # Step 4: Perform diagnostic checks
        # In a real model-backed agent, you would query an LLM here with the
        # prompt and file contents, and execute LLM-generated tool calls.
        if "INVALID" in current_config:
            # Fix malformed setting
            repaired = (
                'BENCH_APP_NAME="Benchmark Catalog"\n'
                'BENCH_CATALOG_ITEMS=["alpha", "beta"]\n'
            )
            environment.write_file(target_file, repaired)
            summary = "Detected invalid BENCH_CATALOG_ITEMS value in .env and repaired with valid JSON list."
            success = True
        else:
            summary = "No configuration defect detected."
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


if __name__ == "__main__":
    # Test the custom agent directly
    agent = CustomDiagnosticAgent()
    print(f"Created custom agent: {agent.name}")
