"""Order lookup, simulated API. Source: design doc lines 174-175, 354-355."""

import json
from pathlib import Path

from pydantic import ValidationError

from src.models import Order

ORDERS_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.json"


class OrderServiceUnavailable(Exception):
    """Simulated outage. Source: design line 382 (--simulate-outage)."""


class OrderDataInvalid(Exception):
    """The customer's own order record is malformed (missing/unparseable dates,
    delivered without a delivery date). Caller escalates instead of guessing."""


def _load_orders() -> list[dict]:
    with open(ORDERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_order(order_id: str, customer_id: str, *, simulate_outage: bool = False) -> dict | None:
    """Returns the order only if it exists AND belongs to customer_id.

    "Not found" and "not owned" return the identical signal (None) on purpose
    (design A7 / line 355): prevents telling the two cases apart and
    enumerating other customers' orders. Validation runs only after the
    ownership check, so a malformed record of another customer is still just
    "not found".
    """
    if simulate_outage:
        raise OrderServiceUnavailable(f"order service unavailable for {order_id}")

    for order in _load_orders():
        if order.get("order_id") == order_id:
            if order.get("customer_id") != customer_id:
                return None
            try:
                Order.model_validate(order)
            except ValidationError as exc:
                raise OrderDataInvalid(order_id) from exc
            return order
    return None
