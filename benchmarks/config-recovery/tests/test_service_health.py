"""Evaluator Module: test_service_health.py (Weight: 20).

Measures: Application starts successfully and health endpoint responds properly.
"""


def test_service_health_endpoint(client):
    """GET /health must return HTTP 200 and status ok."""
    response = client.get("/health")
    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert isinstance(data, dict), "Health response must be a JSON object"
    assert data.get("status") == "ok", f"Expected status 'ok', got {data.get('status')}"
