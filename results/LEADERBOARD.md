# AI Agent Evaluation Benchmarks — Official Leaderboard

> **Last Updated**: 2026-10-24 13:07:11 UTC | **Total Benchmark Trials**: 25

## Agent Capability Rankings

| Rank | Agent | Model | Success@1 | Pass@3 | Mean Score | Cost/Pass | Latency (p50/p95) | Violations |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `scripted-baseline` | `default` | **100.0%** | 100.0% | 100.0/100 | $0.00 | 3.7s / 40.92s | 0.0% |
| **2** | `llm-llm` | `default` | **50.0%** | — | 50.0/100 | $0.0064 | 4.17s / 4.84s | 0.0% |
| **3** | `no-op` | `default` | **0.0%** | 0.0% | 10.8/100 | $0.00 | 3.52s / 3.93s | 0.0% |

## Task Diagnostic Overview

| Task ID | Total Attempts | Passed | Solve Rate | Avg Score | Avg Duration |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `contract-repair-001` | 3 | 1 | **33.3%** | 46.7 | 3.87s |
| `config-recovery-001` | 14 | 10 | **71.4%** | 71.4 | 3.6s |
| `multi-service-cache-001` | 8 | 7 | **87.5%** | 90.6 | 13.31s |
