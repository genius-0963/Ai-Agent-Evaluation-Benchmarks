from fastapi import FastAPI
from pydantic import BaseModel


class OrderItem(BaseModel):
    id: str
    item: str
    amount: float


app = FastAPI(title="Order Service")

ORDERS = [
    OrderItem(id="ord-1", item="Widget A", amount=25.0),
    OrderItem(id="ord-2", item="Widget B", amount=40.0),
]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# BROKEN CONTRACT: Changed 'data' to 'orders', missing 'total', changed 'status' to 'ok'
@app.get("/api/v1/orders")
def get_orders():
    return {
        "orders": [o.model_dump() for o in ORDERS],
        "status": "ok",
    }
