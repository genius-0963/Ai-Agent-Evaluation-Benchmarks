from pathlib import Path

import pytest

from agentbench.workspace import Workspace, WorkspaceSecurityError


def test_workspace_file_operations(tmp_path: Path):
    ws = Workspace(tmp_path)
    ws.write_file("sub/hello.txt", "Hello World!")
    assert ws.read_file("sub/hello.txt") == "Hello World!"
    assert "sub/hello.txt" in ws.list_files()


def test_workspace_rejects_path_traversal(tmp_path: Path):
    ws = Workspace(tmp_path)
    with pytest.raises(WorkspaceSecurityError):
        ws.read_file("../../etc/passwd")

    with pytest.raises(WorkspaceSecurityError):
        ws.write_file("../escape.txt", "malicious")


def test_workspace_search_text(tmp_path: Path):
    ws = Workspace(tmp_path)
    ws.write_file("config.py", "DATABASE_PORT = 5432\nCACHE_PORT = 6379\n")
    results = ws.search_text("DATABASE_PORT")
    assert len(results) == 1
    assert results[0]["file"] == "config.py"
    assert results[0]["line_number"] == 1


def test_workspace_run_allowed_command(tmp_path: Path):
    ws = Workspace(tmp_path)
    # Allowed command: echo
    code, stdout, stderr = ws.run_allowed_command(["echo", "testing"])
    assert code == 0
    assert stdout.strip() == "testing"

    # Disallowed command: rm or bash or curl
    code, stdout, stderr = ws.run_allowed_command(["curl", "https://example.com"])
    assert code == 126
    assert "not permitted" in stderr
