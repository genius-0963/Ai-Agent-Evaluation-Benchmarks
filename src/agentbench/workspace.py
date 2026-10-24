"""Workspace sandboxing, safe tool execution, and anti-tamper filesystem integrity."""

import fnmatch
import hashlib
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any


class WorkspaceSecurityError(Exception):
    """Raised when an operation attempts to escape or violate workspace boundaries."""


class Workspace:
    """Manages an agent-accessible filesystem directory with path validation and safe inspection tools."""

    ALLOWED_COMMANDS = {
        "python",
        "python3",
        "pytest",
        "uvicorn",
        "cat",
        "ls",
        "grep",
        "find",
        "head",
        "tail",
        "echo",
        "pwd",
        "env",
        "diff",
    }

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.security_violations: list[str] = []
        self._initial_hashes: dict[str, str] = {}
        self.snapshot_integrity()

    def snapshot_integrity(self) -> None:
        """Compute SHA-256 hashes of all initial workspace files."""
        self._initial_hashes.clear()
        for root, _, filenames in os.walk(self.root_dir):
            for f in filenames:
                p = Path(root) / f
                rel = str(p.relative_to(self.root_dir))
                try:
                    h = hashlib.sha256(p.read_bytes()).hexdigest()
                    self._initial_hashes[rel] = h
                except Exception:
                    pass

    def check_integrity_violations(
        self, protected_globs: list[str] | None = None
    ) -> list[str]:
        """Verify that protected files were not deleted or modified by untrusted agents."""
        if not protected_globs:
            protected_globs = ["tests/*", "*test*.py", "conftest.py", "Dockerfile"]

        violations = []
        for rel_path, orig_hash in self._initial_hashes.items():
            is_protected = any(
                fnmatch.fnmatch(rel_path, pat) for pat in protected_globs
            )
            if not is_protected:
                continue

            target_file = self.root_dir / rel_path
            if not target_file.is_file():
                v = f"Tampering violation: Protected file '{rel_path}' was deleted."
                violations.append(v)
                self.security_violations.append(v)
            else:
                try:
                    new_hash = hashlib.sha256(target_file.read_bytes()).hexdigest()
                    if new_hash != orig_hash:
                        v = f"Tampering violation: Protected file '{rel_path}' was modified."
                        violations.append(v)
                        self.security_violations.append(v)
                except Exception as e:
                    v = f"Tampering violation: Could not verify hash of '{rel_path}': {e}"
                    violations.append(v)
                    self.security_violations.append(v)

        return violations

    def _resolve_safe_path(self, relative_path: str | Path) -> Path:
        """Resolve a path and ensure it strictly resides within root_dir."""
        raw_path = Path(relative_path)
        if raw_path.is_absolute():
            try:
                candidate = raw_path.resolve()
                candidate.relative_to(self.root_dir)
                return candidate
            except ValueError:
                cleaned = str(raw_path).lstrip("/")
                candidate = (self.root_dir / cleaned).resolve()
        else:
            candidate = (self.root_dir / raw_path).resolve()

        try:
            candidate.relative_to(self.root_dir)
        except ValueError as e:
            violation = f"Path traversal attack detected: '{relative_path}' resolves outside workspace"
            self.security_violations.append(violation)
            raise WorkspaceSecurityError(violation) from e

        return candidate

    def read_file(self, relative_path: str, max_bytes: int = 100_000) -> str:
        """Safely read text file contents up to max_bytes."""
        target = self._resolve_safe_path(relative_path)
        if not target.is_file():
            raise FileNotFoundError(f"File not found in workspace: {relative_path}")

        with open(target, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)

    def write_file(self, relative_path: str, content: str) -> None:
        """Safely write contents to a file in the workspace."""
        target = self._resolve_safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

    def list_files(self, relative_path: str = ".", recursive: bool = True) -> list[str]:
        """List files relative to workspace root."""
        base = self._resolve_safe_path(relative_path)
        if not base.is_dir():
            raise NotADirectoryError(f"Directory not found: {relative_path}")

        files: list[str] = []
        if recursive:
            for root, dirs, filenames in os.walk(base):
                dirs[:] = [
                    d for d in dirs if not d.startswith(".") and d != "__pycache__"
                ]
                for f in sorted(filenames):
                    if f.endswith(".pyc") or f == ".DS_Store":
                        continue
                    full_p = Path(root) / f
                    rel_p = full_p.relative_to(self.root_dir)
                    files.append(str(rel_p))
        else:
            for item in sorted(base.iterdir()):
                if not item.name.startswith(".") and item.name != "__pycache__":
                    files.append(str(item.relative_to(self.root_dir)))
        return files

    def search_text(
        self, query: str, relative_path: str = ".", max_matches: int = 50
    ) -> list[dict[str, Any]]:
        """Search for literal text or regex pattern across workspace files."""
        pattern = re.compile(query, re.IGNORECASE)
        results: list[dict[str, Any]] = []

        files = self.list_files(relative_path, recursive=True)
        for rel_file in files:
            full_path = self.root_dir / rel_file
            if not full_path.is_file():
                continue
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_no, line in enumerate(f, start=1):
                        if pattern.search(line):
                            results.append(
                                {
                                    "file": rel_file,
                                    "line_number": line_no,
                                    "line": line.rstrip(),
                                }
                            )
                            if len(results) >= max_matches:
                                return results
            except Exception:
                continue
        return results

    def apply_patch(self, patch: str) -> bool:
        """Apply a patch or replacement to a file in the workspace."""
        lines = patch.strip().splitlines()
        target_path = None
        for line in lines:
            if line.startswith("+++ b/") or line.startswith("+++ "):
                target_path = line.split(" ", 1)[1].replace("b/", "").strip()
                break

        if target_path:
            self._resolve_safe_path(target_path)
            try:
                proc = subprocess.run(
                    ["patch", "-p1"],
                    input=patch,
                    cwd=str(self.root_dir),
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                if proc.returncode == 0:
                    return True
            except Exception:
                pass

        match = re.match(r"^FILE:\s*([^\n]+)\n(.*)$", patch, re.DOTALL)
        if match:
            fpath = match.group(1).strip()
            content = match.group(2)
            self.write_file(fpath, content)
            return True

        return False

    def run_allowed_command(
        self,
        command: str | list[str],
        timeout_seconds: int = 30,
    ) -> tuple[int, str, str]:
        """Execute an allowed diagnostic/build command in the workspace directory."""
        if isinstance(command, str):
            parts = shlex.split(command)
        else:
            parts = list(command)

        if not parts:
            return 1, "", "Empty command"

        cmd_binary = Path(parts[0]).name
        if cmd_binary not in self.ALLOWED_COMMANDS:
            violation = (
                f"Prohibited tool execution: '{cmd_binary}' violates security policy"
            )
            self.security_violations.append(violation)
            return (
                126,
                "",
                f"Command '{cmd_binary}' is not permitted by workspace security policy.",
            )

        try:
            proc = subprocess.run(
                parts,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command exceeded deadline of {timeout_seconds}s"
        except Exception as e:
            return 1, "", str(e)
