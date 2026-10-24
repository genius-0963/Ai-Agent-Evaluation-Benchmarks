"""Evaluator Module: test_service_health.py (Weight: 20).

Measures: Application startup and health check contract.
"""


def test_service_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
