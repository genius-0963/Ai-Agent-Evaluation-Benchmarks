"""Dual-clock time management separating model inference latency from environment execution."""

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator


@dataclass
class ClockMetrics:
    """Detailed time and token metrics for an evaluation run."""

    inference_duration_seconds: float = 0.0
    execution_duration_seconds: float = 0.0
    total_duration_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    api_call_count: int = 0


class BenchmarkClock:
    """Manages separate timing clocks for AI reasoning vs. task environment execution."""

    def __init__(self) -> None:
        self.wall_clock_start = time.time()
        self.inference_duration = 0.0
        self.execution_duration = 0.0
        self.input_tokens = 0
        self.output_tokens = 0
        self.api_call_count = 0

    @contextmanager
    def measure_inference(self) -> Generator[None, None, None]:
        """Context manager pausing execution clock and recording model inference time."""
        t0 = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - t0
            self.inference_duration += elapsed
            self.api_call_count += 1

    @contextmanager
    def measure_execution(self) -> Generator[None, None, None]:
        """Context manager recording environment and tool execution time."""
        t0 = time.time()
        try:
            yield
        finally:
            self.execution_duration += time.time() - t0

    def record_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Accumulate token consumption from model calls."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens

    def get_metrics(self, model_name: str = "") -> ClockMetrics:
        """Calculate and return snapshot of current clock metrics."""
        total_tokens = self.input_tokens + self.output_tokens
        total_wall = time.time() - self.wall_clock_start

        # Simple price estimate per 1M tokens ($2.50 in / $10.00 out benchmark average)
        cost = (self.input_tokens * 2.50 / 1e6) + (self.output_tokens * 10.00 / 1e6)

        return ClockMetrics(
            inference_duration_seconds=round(self.inference_duration, 2),
            execution_duration_seconds=round(self.execution_duration, 2),
            total_duration_seconds=round(total_wall, 2),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(cost, 4),
            api_call_count=self.api_call_count,
        )
