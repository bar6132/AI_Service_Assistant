"""Deterministic reply guard. Source: design doc section 14 (lines 338-346).

A deny-list can never be complete; this is defense in depth on top of the
facts package, not the only safety layer. What it enforces, in both Hebrew and
English: no foreign order/request numbers, no dates outside the facts package
(any format), no relative deadlines, no commitment language, no amounts, no
internal policy codes.
"""

import re
from datetime import date

from src.order_ids import find_order_ids

# Used as the model-facing must_not_say list (prompt instruction). The guard
# itself checks the wider patterns below, not just these literals.
FORBIDDEN_WORDS = [
    "בוטלה", "אושר", "פיצוי", "החזר כספי מובטח", "תקבל החלפה",
    "cancelled", "approved", "refund", "compensation", "guaranteed",
]

_COMMITMENT = re.compile(
    r"בוטל|אושר|אישרנו|פיצוי|נפצה|נחזיר\s+לך|מובטח|נבטיח|מבטיחים"
    r"|תקבל(?:י|ו)?\s+(?:\S+\s+)?(?:החזר|החלפה|זיכוי)"
    r"|\bcancell?ed\b|\bapproved\b|\bcompensat\w*|\brefund(?:ed|s)?\b|\bguarantee[ds]?\b"
    r"|\bwill\s+(?:receive|get)\s+(?:a\s+|your\s+)?(?:refund|replacement|compensation)",
    re.IGNORECASE,
)
_RELATIVE_TIME = re.compile(
    r"מחרתיים|מחר|בימים הקרובים|בשבוע הבא|תוך\s+\d+\s+(?:ימים|ימי עסקים|שעות)"
    r"|\btomorrow\b|\bnext week\b|\bin the (?:coming|next)(?: few)? days\b"
    r"|\bwithin\s+\d+\s+(?:business\s+)?(?:days|hours)\b",
    re.IGNORECASE,
)
_CURRENCY = re.compile(r"₪|ש\"ח|ש״ח|\bNIS\b|\bILS\b|€|\$\s?\d|\d\s?\$|\bshekels?\b", re.IGNORECASE)
_INTERNAL = re.compile(r"\bPOL-\d{2}\b|agent_handoff|shipping_inquiry|internal_reason|decision_context")
_SR_ID = re.compile(r"(?<![A-Za-z0-9])SR-\d+(?!\d)")

_HE_MONTHS = {
    "ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5, "יוני": 6,
    "יולי": 7, "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12,
}
_EN_MONTHS = {
    name: i for i, names in enumerate(
        [("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
         ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
         ("september", "sept", "sep"), ("october", "oct"), ("november", "nov"), ("december", "dec")],
        start=1,
    ) for name in names
}
_EN_MONTH_ALT = "|".join(sorted(_EN_MONTHS, key=len, reverse=True))
_HE_MONTH_ALT = "|".join(_HE_MONTHS)

_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{2,4})(?!\d)")
_HE_WORD_DATE = re.compile(rf"(?<!\d)(\d{{1,2}})\s+ב?({_HE_MONTH_ALT})(?:\s+(\d{{4}}))?")
_EN_MONTH_FIRST = re.compile(
    rf"\b({_EN_MONTH_ALT})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", re.IGNORECASE
)
_EN_DAY_FIRST = re.compile(
    rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_EN_MONTH_ALT})\b\.?(?:,?\s+(\d{{4}}))?", re.IGNORECASE
)


def _year(raw: str | None) -> int | None:
    if not raw:
        return None
    return 2000 + int(raw) if len(raw) == 2 else int(raw)


def _mentioned_dates(text: str) -> list[tuple[str, int | None, int, int]]:
    """(raw text, year or None, month, day) for every date written in the text,
    whatever the format: ISO, DD.MM.YYYY, DD/MM/YYYY, "24 בספטמבר",
    "September 24", "24th of September 2026"."""
    found: list[tuple[str, int | None, int, int]] = []
    for m in _ISO_DATE.finditer(text):
        found.append((m.group(0), int(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _NUMERIC_DATE.finditer(text):
        found.append((m.group(0), _year(m.group(3)), int(m.group(2)), int(m.group(1))))
    for m in _HE_WORD_DATE.finditer(text):
        found.append((m.group(0), _year(m.group(3)), _HE_MONTHS[m.group(2)], int(m.group(1))))
    for m in _EN_MONTH_FIRST.finditer(text):
        found.append((m.group(0), _year(m.group(3)), _EN_MONTHS[m.group(1).lower()], int(m.group(2))))
    for m in _EN_DAY_FIRST.finditer(text):
        found.append((m.group(0), _year(m.group(3)), _EN_MONTHS[m.group(2).lower()], int(m.group(1))))
    return found


def _parse_date(raw: str) -> date | None:
    """Facts-package dates are ISO; DD.MM.YYYY is accepted too. Found in testing
    (case 5, part 10): the model wrote "12.09.2026" for "2026-09-12" — same
    day, different string — and a naive string compare flagged a correct date."""
    parsed = _mentioned_dates(raw)
    if not parsed:
        return None
    _, y, m, d = parsed[0]
    try:
        return date(y, m, d) if y else None
    except ValueError:
        return None


def check(reply: str, order_id: str | None, allowed_dates: list[str], service_request_id: str | None) -> list[str]:
    """Returns violation descriptions; empty list = reply passed the guard."""
    violations: list[str] = []

    leaked_orders = set(find_order_ids(reply)) - ({order_id} if order_id else set())
    if leaked_orders:
        violations.append(f"מספר הזמנה לא מורשה בתשובה: {sorted(leaked_orders)}")

    allowed = [d for d in (_parse_date(a) for a in allowed_dates) if d is not None]
    for raw, y, m, d in _mentioned_dates(reply):
        if not any((a.month, a.day) == (m, d) and (y is None or a.year == y) for a in allowed):
            violations.append(f"תאריך שלא מופיע בחבילת העובדות: {raw}")

    for rx, label in (
        (_COMMITMENT, "לשון התחייבות אסורה"),
        (_RELATIVE_TIME, "מועד יחסי (הבטחת מועד)"),
        (_CURRENCY, "סכום/מטבע"),
        (_INTERNAL, "קוד או מונח פנימי"),
    ):
        hit = rx.search(reply)
        if hit:
            violations.append(f"{label}: {hit.group(0)}")

    mentioned_srs = set(_SR_ID.findall(reply))
    foreign_srs = mentioned_srs - ({service_request_id} if service_request_id else set())
    if foreign_srs:
        violations.append(f"מספר בקשה לא מורשה בתשובה: {sorted(foreign_srs)}")
    if service_request_id and service_request_id not in mentioned_srs:
        violations.append("מספר בקשת השירות לא מופיע בתשובה")

    return violations


_FALLBACK_TEMPLATES = {
    "he": {
        "reply_with_sr": "הבקשה שלך נקלטה במערכת, מספר בקשה {sr_id}. הבקשה בבדיקה ואינה מהווה אישור סופי לתוצאה.",
        "reply_no_sr": "בדקתי את הפנייה שלך במערכת. לצערי אין לי מידע נוסף מעבר לכך במסגרת המדיניות הקיימת.",
        "clarify": "כדי להמשיך בבירור הפנייה אני צריך/ה פרט נוסף ממך — תוכל/י לפרט?",
        "escalate_with_sr": "העברתי את הפנייה שלך לנציג אנושי, מספר פנייה {sr_id}. נציג יחזור אליך; אין באפשרותי להבטיח את תוצאת הטיפול.",
        "escalate_no_sr": "העברתי את הפנייה שלך לנציג אנושי לבירור נוסף. נציג יחזור אליך; אין באפשרותי להבטיח את תוצאת הטיפול.",
    },
    "en": {
        "reply_with_sr": "Your request has been received, request number {sr_id}. It is under review and is not a final confirmation of the outcome.",
        "reply_no_sr": "I checked your request in our system, but I have no further information to share under the current policy.",
        "clarify": "To continue with your request I need one more detail from you — could you provide it?",
        "escalate_with_sr": "I've forwarded your request to a human agent, reference number {sr_id}. An agent will get back to you; I can't promise the outcome.",
        "escalate_no_sr": "I've forwarded your request to a human agent for further review. An agent will get back to you; I can't promise the outcome.",
    },
}


def fallback_reply(action: str, service_request_id: str | None, language: str = "he") -> str:
    """Fixed, guaranteed-safe template — design line 345: "אם גם הוא נכשל →
    תבנית קבועה לאותו מצב. כך התשובה תמיד בטוחה, גם כשהיא פחות טבעית"."""
    templates = _FALLBACK_TEMPLATES.get(language, _FALLBACK_TEMPLATES["he"])
    if action == "clarify":
        return templates["clarify"]
    key = f"{action}_{'with_sr' if service_request_id else 'no_sr'}"
    template = templates[key]
    return template.format(sr_id=service_request_id) if service_request_id else template
