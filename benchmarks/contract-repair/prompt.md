# Task: Restore Order Service API Contract

A recent refactor in `app/main.py` broke the contract expected by downstream API consumers.

## Observed Problem
Downstream clients calling `GET /api/v1/orders` are encountering contract deserialization errors.

## Contract Specification
The `GET /api/v1/orders` endpoint must return JSON with the exact structure:
```json
{
  "data": [
    {"id": "ord-1", "item": "Widget A", "amount": 25.0},
    {"id": "ord-2", "item": "Widget B", "amount": 40.0}
  ],
  "total": 2,
  "status": "success"
}
```

## Requirements
- Maintain `GET /health` returning `{"status": "ok"}`.
- Fix `GET /api/v1/orders` in `app/main.py` so that it returns the expected envelope (`data`, `total`, `status`).
- Ensure `total` equals the length of `data`.
- Do not modify evaluation tests or test definitions.
- Keep all existing order items intact.
