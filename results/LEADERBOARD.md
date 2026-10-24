# AI Agent Evaluation Benchmarks — Official Leaderboard

> **Last Updated**: 2026-10-24 12:23:57 UTC | **Total Benchmark Trials**: 8

## Agent Capability Rankings

| Rank | Agent | Model | Success@1 | Pass@3 | Mean Score | Cost/Pass | Latency (p50/p95) | Violations |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `scripted-baseline` | `default` | **100.0%** | 100.0% | 100.0/100 | $0.00 | 3.22s / 3.35s | 0.0% |
| **2** | `no-op` | `default` | **0.0%** | — | 0.0/100 | $0.00 | 3.54s / 3.54s | 0.0% |

## Task Diagnostic Overview

| Task ID | Total Attempts | Passed | Solve Rate | Avg Score | Avg Duration |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `config-recovery-001` | 5 | 4 | **80.0%** | 80.0 | 3.35s |
| `multi-service-cache-001` | 3 | 3 | **100.0%** | 100.0 | 2.97s |
