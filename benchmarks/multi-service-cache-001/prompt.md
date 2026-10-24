# Task: Repair Multi-Service Cache Connection Pool

Downstream requests to the API Gateway are failing with HTTP 500 internal server errors
when fetching user profiles.

## Symptoms
- `GET /health` is responding, but `GET /api/v1/user/profile/{user_id}` fails with 500 Internal Server Error.
- Relevant logs indicate connection errors and pool exhaustion in the caching layer (`app/cache_client.py`).

## Requirements
- Inspect `.env`, `app/config.py`, and `app/cache_client.py`.
- Correct the Redis cache configuration in `.env` so that connection pool size is at least 10 and port is properly configured.
- Ensure `GET /api/v1/user/profile/{user_id}` returns HTTP 200 with user profile and caching metadata.
- Maintain `GET /health` returning `{"status": "ok"}`.
- Preserve fallback mechanism when `nocache=true` is passed.
