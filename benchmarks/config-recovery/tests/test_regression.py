"""Evaluator Module: test_regression.py (Weight: 20).

Measures: Existing API contracts remain intact and no regression occurs.
"""


def test_health_contract_is_preserved(client):
    """Health contract schema and values must not change."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_catalog_items_are_a_list(client):
    """Catalog items must strictly be a list of strings."""
    response = client.get("/api/catalog")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list), "'items' must be a list"
    for item in data["items"]:
        assert isinstance(item, str), f"Item {item} must be a string"


def test_invalid_endpoint_returns_404(client):
    """Unknown endpoints must continue returning 404."""
    response = client.get("/api/non-existent-endpoint")
    assert response.status_code == 404
