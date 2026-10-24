from fastapi import FastAPI
from pydantic import BaseModel


class OrderItem(BaseModel):
    id: str
    item: str
    amount: float


app = FastAPI(title="Order Service")

# Sample order inventory
ORDERS = [
    OrderItem(id="ord-1", item="Widget A", amount=25.0),
    OrderItem(id="ord-2", item="Widget B", amount=40.0),
]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# REPAIRED CONTRACT: Conforms to 'data', 'total', 'status' envelope
@app.get("/api/v1/orders")
def get_orders():
    order_dicts = [o.model_dump() for o in ORDERS]
    return {
        "data": order_dicts,
        "total": len(order_dicts),
        "status": "success",
    }
