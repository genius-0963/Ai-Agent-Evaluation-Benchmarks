#!/usr/bin/env python3
"""Validate all benchmark tasks in the repository for schema compliance and file integrity."""

import sys
from pathlib import Path

from agentbench.task_loader import list_tasks, validate_task_integrity


def main() -> int:
    benchmarks_dir = Path("benchmarks")
    if not benchmarks_dir.is_dir():
        sys.stderr.write(f"Benchmarks directory not found: {benchmarks_dir}\n")
        return 1

    tasks = list_tasks(benchmarks_dir)
    if not tasks:
        sys.stderr.write("No benchmark tasks discovered.\n")
        return 1

    has_errors = False
    print(f"Discovered {len(tasks)} benchmark task(s):")

    for task in tasks:
        errors = validate_task_integrity(task)
        if errors:
            has_errors = True
            print(f"  [FAIL] {task.id} (v{task.version})")
            for err in errors:
                print(f"         • {err}")
        else:
            print(f"  [PASS] {task.id} (v{task.version}) - {task.name}")

    if has_errors:
        print("\nBenchmark validation failed.")
        return 1

    print("\nAll benchmark tasks successfully validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
