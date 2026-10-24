# Security Model and Sandbox Architecture

## Principles

1. **Untrusted Code Execution**: AI coding agents may generate syntactically arbitrary or malicious shell instructions. They must run with zero host privileges.
2. **Evaluation Integrity**: The test suite is the single source of truth and must be completely immutable to the agent.
3. **Reproducible Containment**: Clean environments must be instantiated from pinned container digests.

## Security Controls

- **No Docker Socket Inside Agent Container**:
  Prevent container breakouts by never passing `/var/run/docker.sock` to the agent.
- **Dropped Linux Capabilities**:
  All capabilities are dropped by default (`cap_drop=["ALL"]`).
- **User Demotion**:
  Container processes run as `benchuser` (UID 1000), never root.
- **Resource Caps**:
  Memory limit (`512MB`), CPU quota (`1.0 core`), PID limits (`150`).
- **Network Isolation**:
  `network_mode="none"` prevents external command-and-control communication or secret exfiltration.
- **Path Sanitization**:
  The `Workspace` class blocks directory traversal attacks using canonical resolution checks.
