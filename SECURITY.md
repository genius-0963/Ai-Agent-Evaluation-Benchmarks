# Security Policy

## Threat Model

`ai-agent-evaluation-benchmarks` runs untrusted AI coding agent actions against task code. Because agent code could attempt sandbox escape or denial-of-service, the framework incorporates defense-in-depth:
- No Docker socket mounting inside task containers.
- Linux capabilities dropped (`cap_drop=["ALL"]`).
- Memory and CPU limits strictly configured.
- Host filesystem paths outside the designated workspace are blocked by `Workspace` validation.
- Evaluator tests are isolated from the agent's write scope.

## Reporting a Vulnerability

If you discover a security vulnerability or sandbox escape vulnerability, please report it privately:
- Email: security@example.com
- Do NOT open public GitHub issues for security vulnerabilities.
- We will acknowledge receipt within 48 hours and coordinate a coordinated disclosure timeline.
