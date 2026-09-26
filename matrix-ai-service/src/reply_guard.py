"""Deterministic reply guard. Source: design doc section 14 (lines 338-346)."""

import re
from datetime import date

ORDER_ID_RE = re.compile(r"ORD-\d{4}")
DATE_RE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}|\d{4}-\d{2}-\d{2}")

FORBIDDEN_WORDS = ["בוטלה", "אושר", "פיצוי", "החזר כספי מובטח", "תקבל החלפה"]


def _parse_date(raw: str) -> date | None:
    """Accepts both ISO (order data) and DD.MM.YYYY (how the model/customers
    write dates in Hebrew) so the same calendar day compares equal regardless
    of which format it's written in. Found in testing (case 5, part 10): the
    model wrote "12.09.2026" for a date the facts package listed as
    "2026-09-12" — same day, different string — and a naive string compare
    flagged a correct date as fabricated."""
    try:
        if "." in raw:
            d, m, y = raw.split(".")
            if len(y) == 2:
                y = "20" + y
            return date(int(y), int(m), int(d))
        return date.fromisoformat(raw)
    except ValueError:
        return None


def check(reply: str, order_id: str | None, allowed_dates: list[str], service_request_id: str | None) -> list[str]:
    """Returns violation descriptions; empty list = reply passed the guard."""
    violations: list[str] = []

    mentioned_orders = set(ORDER_ID_RE.findall(reply))
    allowed_orders = {order_id} if order_id else set()
    leaked_orders = mentioned_orders - allowed_orders
    if leaked_orders:
        violations.append(f"מספר הזמנה לא מורשה בתשובה: {leaked_orders}")

    allowed_date_objs = {parsed for d in allowed_dates if (parsed := _parse_date(d)) is not None}
    for raw_date in DATE_RE.findall(reply):
        parsed = _parse_date(raw_date)
        if parsed is None or parsed not in allowed_date_objs:
            violations.append(f"תאריך שלא מופיע בחבילת העובדות: {raw_date}")

    for word in FORBIDDEN_WORDS:
        if word in reply:
            violations.append(f"מילה אסורה בתשובה: {word}")

    if service_request_id and service_request_id not in reply:
        violations.append("מספר בקשת השירות לא מופיע בתשובה")

    return violations


_FALLBACK_TEMPLATES = {
    "reply_with_sr": "הבקשה שלך נקלטה במערכת, מספר בקשה {sr_id}. הבקשה בבדיקה ואינה מהווה אישור סופי לתוצאה.",
    "reply_no_sr": "בדקתי את הפנייה שלך במערכת. לצערי אין לי מידע נוסף מעבר לכך במסגרת המדיניות הקיימת.",
    "clarify": "כדי להמשיך בבירור הפנייה אני צריך/ה פרט נוסף ממך — תוכל/י לפרט?",
    "escalate_with_sr": "העברתי את הפנייה שלך לנציג אנושי, מספר פנייה {sr_id}. נציג יחזור אליך; אין באפשרותי להבטיח את תוצאת הטיפול.",
    "escalate_no_sr": "העברתי את הפנייה שלך לנציג אנושי לבירור נוסף. נציג יחזור אליך; אין באפשרותי להבטיח את תוצאת הטיפול.",
}


def fallback_reply(action: str, service_request_id: str | None) -> str:
    """Fixed, guaranteed-safe template — design line 345: "אם גם הוא נכשל →
    תבנית קבועה לאותו מצב. כך התשובה תמיד בטוחה, גם כשהיא פחות טבעית"."""
    if action == "clarify":
        return _FALLBACK_TEMPLATES["clarify"]
    key = f"{action}_{'with_sr' if service_request_id else 'no_sr'}"
    template = _FALLBACK_TEMPLATES[key]
    return template.format(sr_id=service_request_id) if service_request_id else template
