import json

from fastapi import FastAPI, HTTPException, Query, Response

from app.cache_client import ConnectionPoolExhaustedError, cache_client

app = FastAPI(title="API Gateway with Distributed Cache")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/user/profile/{user_id}")
def get_user_profile(
    user_id: int,
    response: Response,
    nocache: bool = Query(default=False),
) -> dict:
    if nocache:
        response.headers["X-Cache"] = "BYPASS"
        if user_id == 42:
            return {"user_id": 42, "name": "Alice Johnson", "tier": "enterprise"}
        elif user_id == 101:
            return {"user_id": 101, "name": "Bob Smith", "tier": "standard"}
        else:
            raise HTTPException(status_code=404, detail="User not found")

    cache_key = f"user:{user_id}"
    try:
        cached_data = cache_client.get(cache_key)
    except ConnectionPoolExhaustedError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Downstream service failure: {e}",
        ) from e

    if cached_data:
        response.headers["X-Cache"] = "HIT"
        return json.loads(cached_data)

    raise HTTPException(status_code=404, detail="User not found")
