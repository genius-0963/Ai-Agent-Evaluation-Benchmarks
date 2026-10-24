# Known Limitations & Non-Goals for Version 0.1.0

## Current Scope Limits

1. **Single-Agent Evaluation**:
   v0.1.0 evaluates a single agent on a single software repair task. Multi-agent coordination and peer reviews are scheduled for subsequent releases.

2. **Linux Containers vs MicroVMs**:
   Docker containers share the host kernel. For public, multi-tenant evaluation platforms accepting arbitrary public code submissions, Firecracker microVMs or gVisor are recommended.

3. **Stateless Tasks**:
   The initial benchmark focuses on configuration recovery and web service lifecycle. Distributed state management (e.g., PostgreSQL clusters or Redis failover) is covered in the expansion roadmap.
