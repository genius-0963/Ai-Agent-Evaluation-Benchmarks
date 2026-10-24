# Key Architectural Decisions (ADRs)

## ADR 1: Independent Pytest Evaluator Over In-Container Test Scripts
*Decision*: Keep evaluation tests outside the agent's `/workspace` directory.
*Rationale*: If tests are inside the workspace, a model could edit `assert True` or delete failing tests to fake a passing score. Keeping tests in a trusted directory guarantees measurement integrity.

## ADR 2: Dual Mode Execution (Docker and Local Sandbox)
*Decision*: Support both Dockerized container runs (`--docker`) and local workspace isolation with path confinement.
*Rationale*: Enables rapid iteration in CI environments where Docker-in-Docker may not be available, while offering maximum isolation for untrusted runs.

## ADR 3: Typed Pydantic Schemas with JSON Schema Validation
*Decision*: Enforce dual validation (Pydantic v2 domain models and JSON Schema 2020-12 draft validation).
*Rationale*: Provides strict type safety during Python execution and machine-readable interoperability for external consumers and dashboards.
