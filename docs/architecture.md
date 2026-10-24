# System Architecture & Design

## 1. Overview

`agentbench` evaluates autonomous AI agents on real-world software repair benchmarks. The framework is designed around five modular components:
1. **Task Loader**: Discovers, parses, and validates `task.yaml` declarations and workspace assets.
2. **Docker Manager**: Orchestrates isolated, disposable container instances with cgroup constraints and dropped capabilities.
3. **Agent Adapter**: Provides a uniform, provider-agnostic interface and exposes restricted diagnostic tools (`read_file`, `write_file`, `list_files`, `search_text`, `run_allowed_command`).
4. **Independent Evaluator**: Executes trusted pytest test modules located strictly outside the agent's write scope.
5. **Scorer & Reporter**: Computes weighted scores across criteria and persists standardized JSON reports with full execution traces.

## 2. Separation of Concerns

```
+--------------------------------------------------------+
|                      Benchmark CLI                     |
+--------------------------------------------------------+
                           |
                           v
+--------------------------------------------------------+
|                     Benchmark Runner                   |
|  - Owns end-to-end lifecycle and resource cleanup      |
+--------------------------------------------------------+
      |                           |                  |
      v                           v                  v
+----------------+      +------------------+  +-------------------+
| Docker Manager |      |  Agent Adapter   |  |     Evaluator     |
| (Sandbox,      |      |  (Solve loop &   |  |  (Correctness &   |
|  Limits)       |      |   Tool budgets)  |  |   Regression)     |
+----------------+      +------------------+  +-------------------+
                                                      |
                                                      v
                                              +-------------------+
                                              | Scorer & Reporter |
                                              +-------------------+
```

- **Harness**: Owns lifecycle, quotas, and cleanup.
- **Agent**: Owns diagnosis and code repair actions.
- **Evaluator**: Owns correctness and verification truth.
- **Scorer**: Owns mathematical weighting and status classification.
- **Reporter**: Owns report serialization and artifact preservation.
