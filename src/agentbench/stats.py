"""Statistical evaluation, Pass@k estimation, confidence intervals, and metrics."""

import math
from dataclasses import dataclass, field
from typing import Sequence

from agentbench.models import BenchmarkReport, RunStatus


@dataclass
class StatisticalSummary:
    """Comprehensive statistical metrics across repeated evaluation trials."""

    task_id: str
    agent_name: str
    trials_count: int
    success_count: int

    # Functional Success & Reliability
    success_at_1: float  # Fraction of tasks passed on first attempt
    pass_at_k: dict[int, float] = field(default_factory=dict)  # k -> pass@k probability

    # Score distribution
    mean_score: float = 0.0
    score_variance: float = 0.0
    score_std_dev: float = 0.0
    confidence_interval_95: tuple[float, float] = (0.0, 0.0)

    # Latency distribution (seconds)
    median_latency_seconds: float = 0.0
    p95_latency_seconds: float = 0.0
    mean_inference_latency_seconds: float = 0.0
    mean_execution_latency_seconds: float = 0.0

    # Efficiency & Cost
    mean_tool_calls: float = 0.0
    total_tokens: int = 0
    mean_tokens_per_trial: float = 0.0
    total_cost_usd: float = 0.0
    cost_per_successful_pass_usd: float = 0.0

    # Safety & Reliability Rates
    violation_rate: float = 0.0
    regression_rate: float = 0.0
    timeout_rate: float = 0.0


def calculate_pass_at_k(n: int, c: int, k: int) -> float:
    """Calculate unbiased pass@k estimator (Chen et al., HumanEval).

    Formula:
      pass@k = 1.0 - prod_{i=1}^k (n - c - i + 1) / (n - i + 1)
      If (n - c) < k, pass@k = 1.0.
    """
    if n <= 0 or k <= 0 or k > n:
        return 0.0
    if c <= 0:
        return 0.0
    if n - c < k:
        return 1.0

    prod = 1.0
    for i in range(1, k + 1):
        prod *= (n - c - i + 1) / (n - i + 1)
    return round(1.0 - prod, 4)


def percentile(data: Sequence[float], p: float) -> float:
    """Calculate p-th percentile from a sequence of values."""
    if not data:
        return 0.0
    sorted_d = sorted(data)
    idx = (len(sorted_d) - 1) * p
    floor_idx = int(math.floor(idx))
    ceil_idx = int(math.ceil(idx))
    if floor_idx == ceil_idx:
        return sorted_d[floor_idx]
    return sorted_d[floor_idx] * (ceil_idx - idx) + sorted_d[ceil_idx] * (
        idx - floor_idx
    )


def compute_statistical_summary(
    reports: list[BenchmarkReport],
    k_values: list[int] | None = None,
) -> StatisticalSummary:
    """Aggregate a collection of evaluation trial reports into statistical metrics."""
    if not reports:
        raise ValueError("Cannot compute statistics on empty report list.")

    n = len(reports)
    task_id = reports[0].task_id
    agent_name = reports[0].agent.name
    k_values = k_values or [1, min(3, n), min(5, n)]
    k_values = sorted(list(set(k for k in k_values if 1 <= k <= n)))

    # Successes (passed status)
    successes = sum(1 for r in reports if r.status == RunStatus.PASSED)
    success_at_1 = round(successes / n, 4)

    # Pass@k for requested k
    pass_k_dict: dict[int, float] = {}
    for k in k_values:
        pass_k_dict[k] = calculate_pass_at_k(n, successes, k)

    # Scores
    scores = [r.score for r in reports]
    mean_score = sum(scores) / n

    if n > 1:
        variance = sum((s - mean_score) ** 2 for s in scores) / (n - 1)
        std_dev = math.sqrt(variance)
        # 95% margin of error using critical value ~1.96 (or 2.0 for small sample)
        t_crit = 1.96 if n >= 30 else 2.1
        margin = t_crit * (std_dev / math.sqrt(n))
        ci_95 = (
            max(0.0, round(mean_score - margin, 2)),
            min(100.0, round(mean_score + margin, 2)),
        )
    else:
        variance = 0.0
        std_dev = 0.0
        ci_95 = (round(mean_score, 2), round(mean_score, 2))

    # Latencies
    durations = [r.duration_seconds for r in reports]
    med_latency = percentile(durations, 0.50)
    p95_latency = percentile(durations, 0.95)

    mean_inf = sum(r.inference_latency_seconds for r in reports) / n
    mean_exec = sum(r.execution_latency_seconds for r in reports) / n

    # Efficiency
    tool_counts = [r.agent.tool_calls for r in reports]
    mean_tools = round(sum(tool_counts) / n, 1)

    tokens = [r.total_tokens for r in reports]
    total_tokens = sum(tokens)
    mean_tokens = round(total_tokens / n, 1)

    costs = [r.cost_usd for r in reports]
    total_cost = sum(costs)
    cost_per_pass = round(total_cost / successes, 4) if successes > 0 else 0.0

    # Safety & Reliability rates
    violations = sum(1 for r in reports if r.security_violations)
    regressions = sum(1 for r in reports if r.regression_detected)
    timeouts = sum(1 for r in reports if r.status == RunStatus.TIMEOUT)

    return StatisticalSummary(
        task_id=task_id,
        agent_name=agent_name,
        trials_count=n,
        success_count=successes,
        success_at_1=success_at_1,
        pass_at_k=pass_k_dict,
        mean_score=round(mean_score, 2),
        score_variance=round(variance, 2),
        score_std_dev=round(std_dev, 2),
        confidence_interval_95=ci_95,
        median_latency_seconds=round(med_latency, 2),
        p95_latency_seconds=round(p95_latency, 2),
        mean_inference_latency_seconds=round(mean_inf, 2),
        mean_execution_latency_seconds=round(mean_exec, 2),
        mean_tool_calls=mean_tools,
        total_tokens=total_tokens,
        mean_tokens_per_trial=mean_tokens,
        total_cost_usd=round(total_cost, 4),
        cost_per_successful_pass_usd=cost_per_pass,
        violation_rate=round(violations / n, 4),
        regression_rate=round(regressions / n, 4),
        timeout_rate=round(timeouts / n, 4),
    )
