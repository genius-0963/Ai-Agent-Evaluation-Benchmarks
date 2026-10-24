"""Evaluator Module: test_behavior.py (Weight: 40).

Measures: GET /api/v1/orders strictly conforms to required response envelope.
"""


def test_orders_envelope_keys(client):
    """Envelope must contain 'data', 'total', and 'status'."""
    response = client.get("/api/v1/orders")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()

    assert "data" in body, "Response envelope must contain 'data' field"
    assert "total" in body, "Response envelope must contain 'total' field"
    assert "status" in body, "Response envelope must contain 'status' field"


def test_orders_envelope_values_and_types(client):
    """Envelope field values and types must match contract specification."""
    response = client.get("/api/v1/orders")
    assert response.status_code == 200
    body = response.json()

    assert isinstance(body["data"], list), "'data' must be a list of order objects"
    assert isinstance(body["total"], int), "'total' must be an integer"
    assert body["status"] == "success", (
        f"Expected status 'success', got '{body['status']}'"
    )
    assert body["total"] == len(body["data"]), (
        f"Total {body['total']} does not match data length {len(body['data'])}"
    )


def test_order_item_schema(client):
    """Each order in data must have id, item, and amount fields."""
    response = client.get("/api/v1/orders")
    body = response.json()

    for order in body.get("data", []):
        assert "id" in order, "Order item missing 'id'"
        assert "item" in order, "Order item missing 'item'"
        assert "amount" in order, "Order item missing 'amount'"
        assert isinstance(order["amount"], (int, float))
