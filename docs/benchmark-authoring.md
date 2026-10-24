# Benchmark Authoring Guide

Guidelines for creating new benchmark tasks for `agentbench`.

## Directory Structure

Each task lives in `benchmarks/<task-id>/`:
```
benchmarks/<task-id>/
├── task.yaml           # Schema definition
├── prompt.md           # Instructions presented to the agent
├── Dockerfile          # Pinned base image & environment
├── fixtures/           # Broken and ground-truth reference files
│   ├── broken.env
│   └── repaired.env
├── app/                # Target application codebase
└── tests/              # Independent evaluator tests
    ├── conftest.py
    ├── test_configuration.py
    ├── test_service_health.py
    ├── test_behavior.py
    └── test_regression.py
```

## Rules for Benchmark Authors

1. **Deterministic Defects**:
   - The initial state must fail 100% of the time for a well-defined reason.
   - Do not rely on timing race conditions or random generation.

2. **No Secret Tests in Workspace**:
   - The agent's workspace must not contain the evaluation test files or expected answers.
   - The independent evaluator imports or execs against the workspace from outside.

3. **Anti-Hardcoding**:
   - Behavior tests must assert that responses come from configured application logic, not hardcoded strings in route handlers.

4. **Task Validation**:
   - Always run `agentbench validate <task-id>` and `agentbench smoke-test <task-id>` before committing.
