"""Orchestrator. Source: design doc section 8 flowchart (lines 110-147),
section 6 automation boundaries (lines 79-88), section 11 decision table
(lines 269-289), section 16 failure handling (lines 377-385)."""

import logging
import re
import sqlite3
import uuid
from datetime import date

from src.llm import AllProvidersFailed, run_structured, run_text
from src.models import AgentInput, AgentResponse, Extraction, ServiceRequestRef
from src.order_ids import find_order_ids
from src.order_service import OrderDataInvalid, OrderServiceUnavailable, get_order
from src.policy_engine import Decision, decide
from src.prompts import build_extraction_system, build_reply_system
from src.reply_guard import FORBIDDEN_WORDS, check as guard_check, fallback_reply
from src.service_requests import create_request

logger = logging.getLogger("agent")

# Fixed replies for the branches that never reach LLM #2 (design diagram nodes
# N/F, lines 124-126, and line 86), in the customer's language (A5). The
# "*_forwarded" texts are used only after an agent_handoff record was actually
# written (A6); if that write fails too, "tech_failure" is used, which does not
# claim anything was forwarded.
MESSAGES = {
    "he": {
        "not_found": "לא מצאתי הזמנה עם המספר הזה בחשבון שלך. תוכל/י לבדוק את מספר ההזמנה?",
        "ask_order_id": "לאיזה מספר הזמנה מתייחסת הפנייה?",
        "ask_one_order": "צוינו כמה מספרי הזמנה בפנייה — לאיזו הזמנה בדיוק את/ה מתכוון/ת?",
        "extraction_failed_forwarded": "מצטערים, לא ניתן להשלים את הבקשה כרגע. הפנייה הועברה לבדיקה.",
        "outage_forwarded": "לא ניתן לבדוק את ההזמנה כרגע עקב תקלה טכנית. הפנייה הועברה לבירור נוסף.",
        "data_invalid_forwarded": "לא ניתן להשלים את בדיקת ההזמנה באופן אוטומטי כרגע. הפנייה הועברה לנציג לבירור.",
        "tech_failure": "לא ניתן להשלים את הבקשה כרגע עקב תקלה טכנית. אנא נסו שוב בעוד מספר דקות.",
    },
    "en": {
        "not_found": "I couldn't find an order with that number on your account. Could you check the order number?",
        "ask_order_id": "Which order number is your request about?",
        "ask_one_order": "Your message mentions more than one order — which order do you mean?",
        "extraction_failed_forwarded": "Sorry, we can't complete your request right now. It has been forwarded for review.",
        "outage_forwarded": "We can't check the order right now due to a technical issue. Your request has been forwarded for follow-up.",
        "data_invalid_forwarded": "We can't complete the automatic check of this order right now. Your request has been forwarded to an agent.",
        "tech_failure": "We can't complete your request right now due to a technical issue. Please try again in a few minutes.",
    },
}

_HEBREW = re.compile(r"[֐-׿]")
_POLICY_CODES = re.compile(r"[\s,+]*POL-\d{2}")


def _message_language(text: str) -> str:
    """Used only before extraction succeeded (no model-detected language yet)."""
    return "he" if _HEBREW.search(text) else "en"


def _final(intent, action, reply, order_id, source_ids, sr_ref, reason) -> AgentResponse:
    return AgentResponse(
        intent=intent, action=action, reply=reply, order_id=order_id,
        source_ids=source_ids, service_request=sr_ref, reason=reason,
    )


def _handoff(customer_id: str, order_id: str | None, reason: str, run_id: str) -> str | None:
    """A6: every escalate leaves an agent_handoff record for staff. Returns the
    record id, or None if even this write failed (caller must then not claim
    the request was forwarded)."""
    try:
        return create_request(
            customer_id=customer_id, order_id=order_id, type_="agent_handoff",
            source_ids=["POL-07"], summary=reason, run_id=run_id,
        )
    except sqlite3.Error:
        logger.exception("handoff.create_failed run_id=%s", run_id)
        return None


def _technical_escalation(intent, lang, customer_id, order_id, reason, forwarded_key, run_id) -> AgentResponse:
    sr_id = _handoff(customer_id, order_id, reason, run_id)
    if sr_id:
        reply, staff_reason = MESSAGES[lang][forwarded_key], f"{reason} — נפתחה העברה לנציג {sr_id}"
    else:
        reply, staff_reason = MESSAGES[lang]["tech_failure"], f"{reason} — גם רישום ההעברה נכשל"
    # The handoff id stays staff-side (reason): the response contract ties a
    # service_request to a confirmed order (design line 262), which these
    # paths never have.
    return _final(intent, "escalate", reply, None, ["POL-07"], None, staff_reason)


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

    must_not_say = FORBIDDEN_WORDS + [
        "מועד אספקה חדש", "סכום פיצוי מדויק", "קודי מדיניות (POL-xx) או מונחים פנימיים של המערכת",
    ]

    # The staff-only reason (design §7: "reason — לצוות בלבד") reaches the model
    # without its policy codes, only as context for phrasing.
    decision_context = _POLICY_CODES.sub("", decision.reason).strip(" ,")
    facts_text = (
        f"order_id: {order['order_id']}\n"
        f"status: {order['status']}\n"
        f"estimated_delivery: {order.get('estimated_delivery')}\n"
        f"delivered_at: {order.get('delivered_at')}\n"
        f"service_request: {sr_ref.model_dump() if sr_ref else None}\n"
        f"decision_context: {decision_context}\n"
    )
    return allowed_dates, must_say, must_not_say, facts_text


def _compose_reply(decision: Decision, order: dict, sr_ref: ServiceRequestRef | None, language: str, intent: str) -> str:
    """LLM #2 + Reply Guard, with the retry-then-fallback rule from design
    line 345: "ניסיון ניסוח אחד נוסף. אם גם הוא נכשל → תבנית קבועה". The retry
    tells the model what the guard rejected — at temperature=0 an identical
    prompt would just return the identical draft."""
    allowed_dates, must_say, must_not_say, facts_text = _facts_and_guardrails(decision, order, sr_ref, intent)
    system = build_reply_system(language, must_say, must_not_say)
    sr_id = sr_ref.id if sr_ref else None
    prompt = facts_text

    for attempt_num in range(1, 3):  # original attempt + one retry
        try:
            reply_text = run_text(system, prompt)
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
        prompt = (
            facts_text
            + "\n\nהטיוטה הקודמת נפסלה בבדיקה האוטומטית בגלל: "
            + "; ".join(violations)
            + ". נסח מחדש בלי אלה."
        )

    logger.warning("guard.fallback order_id=%s action=%s", order["order_id"], decision.action)
    return fallback_reply(decision.action, sr_id, language)


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
        # A8 (design line 75): a clarification answer is checked in a fresh run
        # that carries what was asked. The context is structured
        # ("return:ORD-1003") and rendered by code into a fixed sentence, so it
        # is not a second free-text channel into the model.
        ctx_intent, ctx_order = agent_input.context.split(":")
        user_text = (
            f"{agent_input.message}\n\n"
            f"הקשר קודם מהשיחה: הלקוח עונה לשאלת הבהרה בנושא {ctx_intent} עבור הזמנה {ctx_order}"
        )

    # LLM #1 — extraction only. Never sees order data (design line 146).
    try:
        extraction: Extraction = run_structured(build_extraction_system(), user_text, Extraction)
    except AllProvidersFailed:
        return _technical_escalation(
            "other", _message_language(agent_input.message), customer_id, None,
            "כשל בכל ספקי המודל בשלב החילוץ", "extraction_failed_forwarded", run_id,
        )
    lang = extraction.language

    # Grounding (design §7: the model finds the order number, the code verifies
    # it): only ids that are actually written in the customer's text (or the
    # clarification context) survive. A hallucinated or injected id — even one
    # that belongs to this customer — never reaches get_order.
    written = set(find_order_ids(user_text))
    order_ids = [oid for oid in extraction.order_ids if oid in written]
    if len(order_ids) < len(extraction.order_ids):
        logger.warning("grounding.drop run_id=%s proposed=%d kept=%d", run_id, len(extraction.order_ids), len(order_ids))

    # design table rows, lines 288-289 — before any order lookup.
    if len(order_ids) == 0:
        return _final(extraction.intent, "clarify", MESSAGES[lang]["ask_order_id"],
                      None, ["POL-07"], None, "לא צוין מספר הזמנה בפנייה")
    if len(order_ids) > 1:
        return _final(extraction.intent, "clarify", MESSAGES[lang]["ask_one_order"],
                      None, ["POL-07"], None, "צוין יותר ממספר הזמנה אחד בפנייה")

    order_id = order_ids[0]

    try:
        order = get_order(order_id, customer_id, simulate_outage=simulate_outage)
    except OrderServiceUnavailable:
        return _technical_escalation(
            extraction.intent, lang, customer_id, order_id,
            "שירות ההזמנות אינו זמין כרגע", "outage_forwarded", run_id,
        )
    except OrderDataInvalid:
        return _technical_escalation(
            extraction.intent, lang, customer_id, order_id,
            "נתוני ההזמנה במערכת אינם תקינים", "data_invalid_forwarded", run_id,
        )

    if order is None:
        # "not found" and "not owned by this customer" are indistinguishable
        # on purpose (A7, design line 355) — prevents enumerating other
        # customers' orders. POL-01 covers ownership.
        return _final(extraction.intent, "reply", MESSAGES[lang]["not_found"], None, ["POL-01"], None,
                      "ההזמנה לא נמצאה בחשבון הלקוח המחובר, או ששייכת ללקוח אחר")

    # From here on the order is confirmed to exist and belong to customer_id —
    # policy_engine.decide() may run (design line 271).
    decision = decide(extraction.intent, order, extraction.product_state, today)

    sr_ref = None
    if decision.service_request_type is not None:
        # SR opened BEFORE composing the reply, so the SR number quoted in the
        # reply is real (design line 147). If the write fails, no number is
        # quoted and nothing is claimed as forwarded (design line 384).
        try:
            sr_id = create_request(
                customer_id=customer_id, order_id=order_id, type_=decision.service_request_type,
                source_ids=decision.source_ids, summary=decision.reason, run_id=run_id,
            )
        except sqlite3.Error:
            logger.exception("sr.create_failed run_id=%s order_id=%s", run_id, order_id)
            return _final(extraction.intent, "escalate", MESSAGES[lang]["tech_failure"], order_id,
                          ["POL-07"], None, "כשל בכתיבת בקשת שירות — לא נוצרה בקשה")
        sr_ref = ServiceRequestRef(type=decision.service_request_type, id=sr_id)

    reply_text = _compose_reply(decision, order, sr_ref, lang, extraction.intent)

    return _final(
        extraction.intent, decision.action, reply_text, order_id,
        decision.source_ids, sr_ref, decision.reason,
    )
