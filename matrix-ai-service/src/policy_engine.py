"""Decision table. Source: AI_Service_Assistant_Design.md section 11 (lines 269-289).

Runs only after the order was found and confirmed to belong to the customer
(design line 271: "רץ רק אחרי שההזמנה נמצאה ושייכת ל-customer_id").
The "no order number" / "more than one order number" -> clarify rules (design
lines 288-289) happen before this, in the orchestrator, since they don't need
an order at all.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from src.models import Intent, PolicyId

RETURN_WINDOW_DAYS = 14


@dataclass
class Decision:
    action: str  # "reply" | "clarify" | "escalate"
    service_request_type: str | None
    source_ids: list[PolicyId]
    reason: str


def _eta_passed_not_delivered(order: dict, today: date) -> bool:
    if order["delivered_at"] is not None:
        return False
    eta = date.fromisoformat(order["estimated_delivery"])
    return today > eta


def _within_return_window(order: dict, today: date) -> bool:
    delivered = date.fromisoformat(order["delivered_at"])
    return today <= delivered + timedelta(days=RETURN_WINDOW_DAYS)


def decide(intent: Intent, order: dict, product_state: str, today: date) -> Decision:
    if intent in ("order_status", "delivery_delay"):
        if _eta_passed_not_delivered(order, today):
            return Decision(
                "reply", "shipping_inquiry", ["POL-03", "POL-02"],
                "ETA עבר וההזמנה טרם נמסרה — נפתחה בקשת בירור משלוח, POL-03",
            )
        return Decision(
            "reply", None, ["POL-02"],
            "מציג סטטוס ותאריך אספקה משוער כהערכה בלבד, POL-02",
        )

    if intent == "cancel":
        if order["status"] == "processing":
            return Decision(
                "reply", "cancellation", ["POL-04"],
                "הזמנה בסטטוס processing — ניתן לפתוח בקשת ביטול, POL-04",
            )
        if order["status"] == "shipped":
            return Decision(
                "reply", None, ["POL-04"],
                "הזמנה כבר נשלחה — לא ניתן לבטל, אפשר לבחון החזרה לאחר מסירה, POL-04",
            )
        return Decision(
            "reply", None, ["POL-04", "POL-05"],
            "הזמנה כבר נמסרה — ביטול לא רלוונטי, מפנה למסלול החזרה, POL-04+POL-05",
        )

    if intent == "return":
        if order["delivered_at"] is None:
            return Decision(
                "reply", None, ["POL-05"],
                "ההזמנה טרם נמסרה — החזרה אפשרית רק אחרי מסירה, POL-05",
            )
        if not _within_return_window(order, today):
            return Decision(
                "escalate", "agent_handoff", ["POL-05"],
                "חלון ההחזרה (14 יום) חלף — מועבר לנציג ללא הבטחת אישור, POL-05",
            )
        if product_state == "opened":
            return Decision(
                "escalate", "agent_handoff", ["POL-05"],
                "המוצר נפתח — חריגה מתנאי ההחזרה, מועבר לנציג, POL-05",
            )
        if product_state == "unknown":
            return Decision(
                "clarify", None, ["POL-05", "POL-07"],
                "מצב המוצר לא ידוע — יש לברר לפני החלטה, POL-05+POL-07",
            )
        return Decision(
            "reply", "return", ["POL-05"],
            "בתוך חלון 14 הימים והמוצר לא נפתח — נפתחת בקשת החזרה, POL-05",
        )

    if intent == "damaged_item":
        return Decision(
            "escalate", "agent_handoff", ["POL-06"],
            "דיווח על מוצר פגום מועבר תמיד לנציג, ללא הבטחת החלפה/החזר, POL-06",
        )

    return Decision(
        "escalate", "agent_handoff", ["POL-07"],
        "אין מדיניות שמכסה את הפנייה — מועבר לנציג, POL-07",
    )
