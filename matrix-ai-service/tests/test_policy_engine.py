"""Unit tests for the decision table — code only, no model.
Source: design doc section 9, line 197: "בדיקות יחידה לקוד בלבד, בלי מודל".

Covers every row of the decision table (design section 11, lines 273-289)
and the 14-day return-window boundary (assumption A3, line 70), including
the exact dates verified live against the running agent in part 10.
"""

from datetime import date

import pytest

from src.policy_engine import decide

TODAY = date(2026, 9, 22)


def _order(status: str, estimated_delivery: str, delivered_at: str | None) -> dict:
    return {
        "order_id": "ORD-TEST",
        "customer_id": "C-101",
        "status": status,
        "estimated_delivery": estimated_delivery,
        "delivered_at": delivered_at,
    }


def test_order_status_eta_passed_not_delivered_opens_shipping_inquiry():
    order = _order("shipped", "2026-09-01", None)
    d = decide("order_status", order, "unknown", TODAY)
    assert d.action == "reply"
    assert d.service_request_type == "shipping_inquiry"
    assert d.source_ids == ["POL-03", "POL-02"]


def test_order_status_eta_not_passed_is_plain_reply():
    order = _order("shipped", "2026-09-30", None)
    d = decide("order_status", order, "unknown", TODAY)
    assert d.action == "reply"
    assert d.service_request_type is None
    assert d.source_ids == ["POL-02"]


def test_delivery_delay_same_rule_as_order_status():
    order = _order("shipped", "2026-09-01", None)
    d = decide("delivery_delay", order, "unknown", TODAY)
    assert d.action == "reply"
    assert d.service_request_type == "shipping_inquiry"


def test_cancel_processing_opens_cancellation():
    order = _order("processing", "2026-09-25", None)
    d = decide("cancel", order, "unknown", TODAY)
    assert d.action == "reply"
    assert d.service_request_type == "cancellation"
    assert d.source_ids == ["POL-04"]


def test_cancel_shipped_cannot_cancel_no_request():
    order = _order("shipped", "2026-09-24", None)
    d = decide("cancel", order, "unknown", TODAY)
    assert d.action == "reply"
    assert d.service_request_type is None
    assert d.source_ids == ["POL-04"]


def test_cancel_delivered_redirects_to_return():
    order = _order("delivered", "2026-09-12", "2026-09-12")
    d = decide("cancel", order, "unknown", TODAY)
    assert d.action == "reply"
    assert d.service_request_type is None
    assert d.source_ids == ["POL-04", "POL-05"]


def test_return_not_delivered_yet():
    order = _order("shipped", "2026-09-24", None)
    d = decide("return", order, "unopened", TODAY)
    assert d.action == "reply"
    assert d.service_request_type is None
    assert d.source_ids == ["POL-05"]


def test_return_unknown_state_asks_clarify():
    order = _order("delivered", "2026-09-12", "2026-09-12")
    d = decide("return", order, "unknown", TODAY)
    assert d.action == "clarify"
    assert d.service_request_type is None
    assert d.source_ids == ["POL-05", "POL-07"]


def test_return_within_window_unopened_opens_request():
    order = _order("delivered", "2026-09-12", "2026-09-12")
    d = decide("return", order, "unopened", TODAY)
    assert d.action == "reply"
    assert d.service_request_type == "return"
    assert d.source_ids == ["POL-05"]


def test_return_opened_always_escalates_even_within_window():
    order = _order("delivered", "2026-09-12", "2026-09-12")
    d = decide("return", order, "opened", TODAY)
    assert d.action == "escalate"
    assert d.service_request_type == "agent_handoff"


def test_return_window_day_14_inclusive_is_still_allowed():
    # delivered 2026-09-08 -> today is exactly day 14 (A3: inclusive)
    order = _order("delivered", "2026-09-08", "2026-09-08")
    d = decide("return", order, "unopened", TODAY)
    assert d.action == "reply"
    assert d.service_request_type == "return"


def test_return_window_day_15_is_outside_and_escalates():
    # delivered 2026-09-07 -> today is day 15, one day past the window
    order = _order("delivered", "2026-09-07", "2026-09-07")
    d = decide("return", order, "unopened", TODAY)
    assert d.action == "escalate"
    assert d.service_request_type == "agent_handoff"
    assert d.source_ids == ["POL-05"]


def test_damaged_item_always_escalates_regardless_of_state():
    order = _order("delivered", "2026-09-12", "2026-09-12")
    d = decide("damaged_item", order, "opened", TODAY)
    assert d.action == "escalate"
    assert d.service_request_type == "agent_handoff"
    assert d.source_ids == ["POL-06"]


def test_uncovered_intent_escalates_with_pol07():
    order = _order("delivered", "2026-09-12", "2026-09-12")
    d = decide("other", order, "unknown", TODAY)
    assert d.action == "escalate"
    assert d.service_request_type == "agent_handoff"
    assert d.source_ids == ["POL-07"]


@pytest.mark.parametrize("status", ["cancelled", "returned", "on_hold", "refunded"])
@pytest.mark.parametrize("intent", ["order_status", "delivery_delay", "cancel", "return", "damaged_item", "other"])
def test_status_not_covered_by_policy_always_escalates(status, intent):
    # Was G-06: a cancelled order asked to be cancelled was told "already delivered".
    d = decide(intent, _order(status, "2026-09-01", None), "unopened", TODAY)
    assert d.action == "escalate"
    assert d.service_request_type == "agent_handoff"
    assert d.source_ids == ["POL-07"]
