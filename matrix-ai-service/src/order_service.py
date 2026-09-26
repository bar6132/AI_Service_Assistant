"""Order lookup, simulated API. Source: design doc lines 174-175, 354-355."""

import json
from pathlib import Path

ORDERS_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.json"


class OrderServiceUnavailable(Exception):
    """Simulated outage. Source: design line 382 (--simulate-outage)."""


def _load_orders() -> list[dict]:
    with open(ORDERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_order(order_id: str, customer_id: str, *, simulate_outage: bool = False) -> dict | None:
    """Returns the order only if it exists AND belongs to customer_id.

    "Not found" and "not owned" return the identical signal (None) on purpose
    (design A7 / line 355): prevents telling the two cases apart and
    enumerating other customers' orders.
    """
    if simulate_outage:
        raise OrderServiceUnavailable(f"order service unavailable for {order_id}")

    for order in _load_orders():
        if order["order_id"] == order_id:
            return order if order["customer_id"] == customer_id else None
    return None
