"""Evaluator Module: test_regression.py (Weight: 20).

Measures: Regression constraints and preservation of order integrity.
"""


def test_order_values_preserved(client):
    """Ensure order items Widget A and Widget B are preserved."""
    response = client.get("/api/v1/orders")
    assert response.status_code == 200
    body = response.json()
    items = [o["item"] for o in body.get("data", [])]
    assert "Widget A" in items
    assert "Widget B" in items


def test_post_orders_not_allowed(client):
    """POST to /api/v1/orders should remain disallowed (405)."""
    response = client.post("/api/v1/orders", json={})
    assert response.status_code == 405


def test_unknown_route_returns_404(client):
    """Unknown endpoints return 404."""
    response = client.get("/api/v1/unknown")
    assert response.status_code == 404
