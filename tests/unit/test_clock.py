import time

from agentbench.clock import BenchmarkClock


def test_clock_timing_and_token_accumulation():
    clock = BenchmarkClock()

    with clock.measure_inference():
        time.sleep(0.02)
    clock.record_token_usage(input_tokens=100, output_tokens=50)

    with clock.measure_execution():
        time.sleep(0.01)

    metrics = clock.get_metrics()
    assert metrics.inference_duration_seconds > 0.01
    assert metrics.execution_duration_seconds > 0.005
    assert metrics.input_tokens == 100
    assert metrics.output_tokens == 50
    assert metrics.total_tokens == 150
    assert metrics.api_call_count == 1
    assert metrics.estimated_cost_usd > 0.0
