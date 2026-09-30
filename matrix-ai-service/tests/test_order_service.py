import pytest

import src.order_service as order_service
from src.order_service import OrderDataInvalid, OrderServiceUnavailable, get_order


def test_own_order_is_returned():
    assert get_order("ORD-1001", "C-101")["status"] == "processing"


def test_other_customers_order_looks_like_a_missing_one():
    assert get_order("ORD-1005", "C-101") is None
    assert get_order("ORD-9999", "C-101") is None


def test_outage_flag_raises():
    with pytest.raises(OrderServiceUnavailable):
        get_order("ORD-1001", "C-101", simulate_outage=True)


@pytest.mark.parametrize("bad", [
    {"estimated_delivery": None},
    {"estimated_delivery": "25/09/2026"},
    {"status": "delivered", "delivered_at": None},
])
def test_malformed_own_record_raises(monkeypatch, bad):
    record = {"order_id": "ORD-1001", "customer_id": "C-101", "status": "shipped",
              "estimated_delivery": "2026-09-25", "delivered_at": None} | bad
    monkeypatch.setattr(order_service, "_load_orders", lambda: [record])
    with pytest.raises(OrderDataInvalid):
        get_order("ORD-1001", "C-101")


def test_missing_field_raises(monkeypatch):
    record = {"order_id": "ORD-1001", "customer_id": "C-101", "status": "shipped",
              "estimated_delivery": "2026-09-25"}
    monkeypatch.setattr(order_service, "_load_orders", lambda: [record])
    with pytest.raises(OrderDataInvalid):
        get_order("ORD-1001", "C-101")


def test_malformed_record_of_another_customer_is_still_just_not_found(monkeypatch):
    record = {"order_id": "ORD-1001", "customer_id": "C-202", "status": "shipped",
              "estimated_delivery": None, "delivered_at": None}
    monkeypatch.setattr(order_service, "_load_orders", lambda: [record])
    assert get_order("ORD-1001", "C-101") is None
