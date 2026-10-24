"""Evaluator Module: test_regression.py (Weight: 25).

Measures: Regression constraints, bypass mechanisms, error status codes, and input validation.
"""


def test_nocache_bypass_returns_correct_data(client):
    """Ensure nocache=true bypasses cache and populates X-Cache: BYPASS."""
    response = client.get("/api/v1/user/profile/42?nocache=true")
    assert response.status_code == 200
    assert response.headers.get("X-Cache") == "BYPASS"
    body = response.json()
    assert body.get("user_id") == 42
    assert body.get("name") == "Alice Johnson"


def test_nonexistent_user_returns_404(client):
    """Ensure non-existent users return 404 in both cached and bypass modes."""
    cached_resp = client.get("/api/v1/user/profile/99999")
    assert cached_resp.status_code == 404

    bypass_resp = client.get("/api/v1/user/profile/99999?nocache=true")
    assert bypass_resp.status_code == 404


def test_invalid_user_id_validation_error(client):
    """Ensure non-integer user IDs produce HTTP 422 without crashing."""
    response = client.get("/api/v1/user/profile/invalid_id")
    assert response.status_code == 422


def test_unknown_route_returns_404(client):
    """Ensure unknown routes return HTTP 404."""
    response = client.get("/api/v1/undefined")
    assert response.status_code == 404
