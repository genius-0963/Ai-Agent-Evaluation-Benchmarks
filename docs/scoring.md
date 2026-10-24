# Scoring Model Specification

## Normalized Criteria Formula

$$Score = \sum_{i=1}^{n} (Weight_i \times Result_i)$$

Where:
- $Weight_i$ is the configured point weight (sum of all weights $= 100.0$).
- $Result_i \in \{0.0, 1.0\}$ represents binary pass/fail for the corresponding test module.

## Default Weights

```yaml
scoring:
  configuration: 30   # test_configuration.py
  startup: 20         # test_service_health.py
  behavior: 30        # test_behavior.py
  regression: 20      # test_regression.py
```

## Run Status Classifications

| Status | Trigger Condition |
| :--- | :--- |
| `passed` | Total Score $\ge$ `pass_threshold` (default: 80.0) |
| `partial` | $0.0 <$ Total Score $<$ `pass_threshold` |
| `failed` | Total Score $== 0.0$ |
| `timeout` | Agent exceeded `max_runtime_seconds` |
| `infrastructure_error`| Docker daemon failure, image build failure, baseline broken |
| `evaluator_error` | Test harness crash or invalid evaluation setup |
