from pathlib import Path

import pytest

from agentbench.agent_adapter import (
    NoOpAgent,
    ScriptedAgent,
    TaskEnvironment,
    ToolBudgetExceeded,
    get_agent,
)
from agentbench.task_loader import load_task
from agentbench.workspace import Workspace


def test_agent_factory_resolution():
    assert isinstance(get_agent("scripted"), ScriptedAgent)
    assert isinstance(get_agent("no-op"), NoOpAgent)
    with pytest.raises(ValueError):
        get_agent("unknown-agent-name")


def test_tool_call_budget_enforcement(tmp_path: Path):
    task = load_task("config-recovery-001")
    # Artificially set tiny budget
    task.agent.max_tool_calls = 2

    ws = Workspace(tmp_path)
    env = TaskEnvironment(ws, task)

    # 1st call
    env.list_files()
    # 2nd call
    env.list_files()

    # 3rd call must raise ToolBudgetExceeded
    with pytest.raises(ToolBudgetExceeded):
        env.list_files()
