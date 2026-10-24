# Contributing to ai-agent-evaluation-benchmarks

Thank you for your interest in contributing to `ai-agent-evaluation-benchmarks`.

## Development Guidelines

1. **Deterministic Benchmarks**:
   - Every benchmark task must produce a reproducible, deterministic failure.
   - Do not use random numbers, live external network calls, or non-pinned dependencies.

2. **Integrity & Independence**:
   - The agent workspace must never contain evaluation tests or grading criteria.
   - Ground truth assertions must reject hardcoded responses.

3. **Code Quality**:
   - All code must pass `ruff check .`, `ruff format --check .`, and `pytest tests/ -v`.
   - Use Python 3.12+ type annotations for all functions and classes.

## Pull Request Process

1. Fork the repository and create your branch from `main`.
2. Implement your benchmark or feature.
3. Add unit and integration tests covering the new functionality.
4. Run:
   ```bash
   make lint
   make test
   make smoke-test
   ```
5. Submit your pull request with a descriptive title and summary of changes.
