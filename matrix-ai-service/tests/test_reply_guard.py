import pytest

from src.reply_guard import _FALLBACK_TEMPLATES, check, fallback_reply

ORDER, DATES, SR = "ORD-1001", ["2026-09-25"], "SR-000002"


def test_same_day_in_hebrew_format_is_not_a_violation():
    # Regression, part 10 improvement #1: "12.09.2026" is the ISO "2026-09-12".
    reply = "ההזמנה ORD-1003 נמסרה בתאריך 12.09.2026. האם המוצר נפתח?"
    assert check(reply, "ORD-1003", ["2026-09-12", "2026-09-12"], None) == []


@pytest.mark.parametrize("reply", [
    "Your order has been cancelled. SR-000002",
    "Your refund is approved. SR-000002",
    "You will receive compensation. SR-000002",
    "ההזמנה יבוטל בקרוב. SR-000002",
    "ההזמנה בוטלה. SR-000002",
    "הבקשה מאושרת. SR-000002",
    "נחזיר לך את הכסף. SR-000002",
    "תקבל החזר בימים הקרובים. SR-000002",
    "ההחזר מובטח. SR-000002",
    "יגיע ב-26/09/2026. SR-000002",
    "יגיע ב-26.09.2026. SR-000002",
    "It will arrive on September 30. SR-000002",
    "יגיע ב-30 בספטמבר. SR-000002",
    "ההזמנה תגיע מחר. SR-000002",
    "It will arrive within 3 days. SR-000002",
    "יזוכה סכום של 150 ₪. SR-000002",
    "לפי POL-05 הבקשה נקלטה. SR-000002",
    "נפתחה בקשת agent_handoff. SR-000002",
    "ההזמנה ORD-1005 בטיפול. SR-000002",
    "ההזמנה ord-1005 בטיפול. SR-000002",
    "הבקשה נקלטה, מספר SR-0000021.",
    "הבקשה נקלטה, מספר SR-000009.",
    "הבקשה נקלטה.",
])
def test_unsafe_replies_are_flagged(reply):
    assert check(reply, ORDER, DATES, SR) != []


@pytest.mark.parametrize("reply", [
    "שלום רב, בקשתך שמספרה SR-000002 נקלטה במערכת. קליטת הבקשה אינה מהווה אישור סופי לתוצאה.",
    "שלום רב, ההזמנה ORD-1001 בטיפול, תאריך האספקה המשוער הוא 2026-09-25 (הערכה בלבד). מספר בקשה SR-000002.",
    "Your request SR-000002 for order ORD-1001 was received; the estimated delivery date is September 25, 2026 (an estimate only).",
    "אנו מאשרים כי בקשתך נקלטה תחת מספר SR-000002. הפנייה הועברה לטיפולו של נציג אנושי.",
])
def test_safe_replies_pass(reply):
    assert check(reply, ORDER, DATES, SR) == []


@pytest.mark.parametrize("language", sorted(_FALLBACK_TEMPLATES))
@pytest.mark.parametrize("action", ["reply", "clarify", "escalate"])
@pytest.mark.parametrize("sr_id", [None, "SR-000002"])
def test_fallback_templates_pass_their_own_guard(language, action, sr_id):
    if action == "clarify" and sr_id:
        pytest.skip("clarify never carries a service request")
    reply = fallback_reply(action, sr_id, language)
    assert check(reply, ORDER, DATES, sr_id) == []


def test_fallback_follows_customer_language():
    assert fallback_reply("escalate", "SR-000002", "en").startswith("I've forwarded")
    assert fallback_reply("escalate", "SR-000002", "he").startswith("העברתי")
