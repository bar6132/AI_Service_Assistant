"""Orchestrator. Source: design doc section 8 flowchart (lines 110-147),
section 6 automation boundaries (lines 79-88), section 11 decision table
(lines 269-289)."""

import logging
import uuid
from datetime import date

from src.llm import AllProvidersFailed, run_structured, run_text
from src.models import AgentInput, AgentResponse, Extraction, ServiceRequestRef
from src.order_service import OrderServiceUnavailable, get_order
from src.policy_engine import Decision, decide
from src.prompts import build_extraction_system, build_reply_system
from src.reply_guard import FORBIDDEN_WORDS, check as guard_check, fallback_reply
from src.service_requests import create_request

logger = logging.getLogger("agent")

# Literal text from design diagram nodes N/F (line 124, 126) and line 86 —
# these two branches bypass LLM#2 + Reply Guard entirely (see diagram: D's
# "not found"/"service down" edges go straight to a fixed reply, never through
# node H). No order object exists yet to build a facts package from.
NOT_FOUND_REPLY = "לא מצאתי הזמנה עם המספר הזה בחשבון שלך. תוכל/י לבדוק את מספר ההזמנה?"
OUTAGE_REPLY = "לא ניתן לבדוק את ההזמנה כרגע עקב תקלה טכנית. הפנייה הועברה לבירור נוסף."


def _final(intent, action, reply, order_id, source_ids, sr_ref, reason) -> AgentResponse:
    return AgentResponse(
        intent=intent, action=action, reply=reply, order_id=order_id,
        source_ids=source_ids, service_request=sr_ref, reason=reason,
    )


def _facts_and_guardrails(decision: Decision, order: dict, sr_ref: ServiceRequestRef | None, intent: str):
    """Builds the "facts package" for LLM #2 (design line 326-334 shows an
    example for case 3). must_say/must_not_say are instructions to the model,
    not independently verified; allowed_dates IS verified, by the guard."""
    allowed_dates = [d for d in (order.get("estimated_delivery"), order.get("delivered_at")) if d]

    must_say: list[str] = []
    if sr_ref is not None:
        must_say += [f"מספר הבקשה {sr_ref.id}", "הבקשה נקלטה ואינה אישור סופי לתוצאה"]
    if decision.action == "escalate":
        must_say.append("הפנייה הועברה לנציג אנושי")
    if decision.action == "clarify":
        must_say.append("יש לשאול שאלה אחת ממוקדת בלבד, בלי לענות במקום הלקוח")
    if intent in ("order_status", "delivery_delay") and order.get("estimated_delivery"):
        # found in testing (case 1, part 10): without an explicit instruction
        # the model answered "when will it arrive" vaguely instead of quoting
        # the actual ETA, even though it was right there in the facts package.
        must_say.append(
            f"תאריך האספקה המשוער כפי שמופיע במערכת: {order['estimated_delivery']} (הערכה בלבד, לא התחייבות)"
        )

    must_not_say = FORBIDDEN_WORDS + ["מועד אספקה חדש", "סכום פיצוי מדויק"]

    facts_text = (
        f"order_id: {order['order_id']}\n"
        f"status: {order['status']}\n"
        f"estimated_delivery: {order.get('estimated_delivery')}\n"
        f"delivered_at: {order.get('delivered_at')}\n"
        f"service_request: {sr_ref.model_dump() if sr_ref else None}\n"
        f"internal_reason: {decision.reason}\n"
    )
    return allowed_dates, must_say, must_not_say, facts_text


def _compose_reply(decision: Decision, order: dict, sr_ref: ServiceRequestRef | None, language: str, intent: str) -> str:
    """LLM #2 + Reply Guard, with the retry-then-fallback rule from design
    line 345: "ניסיון ניסוח אחד נוסף. אם גם הוא נכשל → תבנית קבועה"."""
    allowed_dates, must_say, must_not_say, facts_text = _facts_and_guardrails(decision, order, sr_ref, intent)
    system = build_reply_system(language, must_say, must_not_say)
    sr_id = sr_ref.id if sr_ref else None

    for attempt_num in range(1, 3):  # original attempt + one retry
        try:
            reply_text = run_text(system, facts_text)
        except AllProvidersFailed:
            logger.warning("guard.compose order_id=%s attempt=%d outcome=llm_failed", order["order_id"], attempt_num)
            break
        violations = guard_check(reply_text, order["order_id"], allowed_dates, sr_id)
        if not violations:
            return reply_text
        logger.warning(
            "guard.reject order_id=%s attempt=%d violations=%d",
            order["order_id"], attempt_num, len(violations),
        )

    logger.warning("guard.fallback order_id=%s action=%s", order["order_id"], decision.action)
    return fallback_reply(decision.action, sr_id)


def handle(
    customer_id: str,
    message: str,
    *,
    today: date,
    context: str | None = None,
    simulate_outage: bool = False,
    run_id: str | None = None,
) -> AgentResponse:
    run_id = run_id or str(uuid.uuid4())
    agent_input = AgentInput(customer_id=customer_id, message=message, context=context)
    user_text = agent_input.message
    if agent_input.context:
        # A8 (design line 75): clarification answers are checked in a fresh
        # run that includes the prior context, not a live conversation.
        user_text = f"{agent_input.message}\n\nהקשר קודם מהשיחה: {agent_input.context}"

    # LLM #1 — extraction only. Never sees order data (design line 146).
    try:
        extraction: Extraction = run_structured(build_extraction_system(), user_text, Extraction)
    except AllProvidersFailed:
        return _final(
            "other", "escalate",
            "מצטערים, לא ניתן להשלים את הבקשה כרגע. הפנייה הועברה לבדיקה.",
            None, ["POL-07"], None, "כשל בכל ספקי המודל בשלב החילוץ",
        )

    # design table rows, lines 288-289 — happens before any order lookup,
    # since there is no order to fetch yet.
    if len(extraction.order_ids) == 0:
        return _final(
            extraction.intent, "clarify", "לאיזה מספר הזמנה מתייחסת הפנייה?",
            None, ["POL-07"], None, "לא צוין מספר הזמנה בפנייה",
        )
    if len(extraction.order_ids) > 1:
        return _final(
            extraction.intent, "clarify",
            "צוינו כמה מספרי הזמנה בפנייה — לאיזו הזמנה בדיוק את/ה מתכוון/ת?",
            None, ["POL-07"], None, "צוין יותר ממספר הזמנה אחד בפנייה",
        )

    order_id = extraction.order_ids[0]

    try:
        order = get_order(order_id, customer_id, simulate_outage=simulate_outage)
    except OrderServiceUnavailable:
        return _final(extraction.intent, "escalate", OUTAGE_REPLY, None, ["POL-07"], None,
                      "שירות ההזמנות אינו זמין כרגע")

    if order is None:
        # "not found" and "not owned by this customer" are indistinguishable
        # on purpose (A7, design line 355) — prevents enumerating other
        # customers' orders. POL-01 covers ownership.
        return _final(extraction.intent, "reply", NOT_FOUND_REPLY, None, ["POL-01"], None,
                      "ההזמנה לא נמצאה בחשבון הלקוח המחובר, או ששייכת ללקוח אחר")

    # From here on the order is confirmed to exist and belong to customer_id —
    # policy_engine.decide() may run (design line 271).
    decision = decide(extraction.intent, order, extraction.product_state, today)

    sr_ref = None
    if decision.service_request_type is not None:
        # SR opened BEFORE composing the reply, so the SR number quoted in the
        # reply is real (design line 147).
        sr_id = create_request(
            customer_id=customer_id, order_id=order_id, type_=decision.service_request_type,
            source_ids=decision.source_ids, summary=decision.reason, run_id=run_id,
        )
        sr_ref = ServiceRequestRef(type=decision.service_request_type, id=sr_id)

    reply_text = _compose_reply(decision, order, sr_ref, extraction.language, extraction.intent)

    return _final(
        extraction.intent, decision.action, reply_text, order_id,
        decision.source_ids, sr_ref, decision.reason,
    )
