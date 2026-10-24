"""Evaluator Module: test_behavior.py (Weight: 25).

Measures: Successful profile retrieval through repaired distributed cache layer.
"""


def test_user_profile_cache_hit(client):
    response = client.get("/api/v1/user/profile/42")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body.get("user_id") == 42
    assert body.get("name") == "Alice Johnson"
    assert response.headers.get("X-Cache") == "HIT"


def test_user_profile_another_id(client):
    response = client.get("/api/v1/user/profile/101")
    assert response.status_code == 200
    body = response.json()
    assert body.get("user_id") == 101
    assert body.get("tier") == "standard"
