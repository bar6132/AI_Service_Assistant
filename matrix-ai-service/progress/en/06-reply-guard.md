# Part 6 — Reply Guard (reply_guard.py)

## What was built
`src/reply_guard.py`: a `check(...)` function that returns a list of violations (empty = OK), and a `fallback_reply(...)` function that returns a fixed, safe template.

## Why it was built this way (source of truth)

**The 4 checks in `check()` are the four exact lines** from the design, section 14 (`Docs/AI_Service_Assistant_Design.md`, lines 340–343):

1. Line 340: "Every order number in the reply = the decision's `order_id`. This prevents leaks" → `mentioned_orders - allowed_orders`; non-empty is a violation.
2. Line 341: "Every date in the reply exists in the facts package. This prevents a new deadline (POL-03)" → `mentioned_dates - allowed_dates`.
3. Line 342: "Forbidden words depending on intent: 'cancelled', 'approved', 'compensation', 'guaranteed refund', 'you'll get a replacement' (POL-04, POL-06)" → `FORBIDDEN_WORDS`, the same list word-for-word.
4. Line 343: "The service-request number appears in the reply when a request was opened" → checks `service_request_id in reply`.

**`fallback_reply()`** implements line 345: "If one check fails: one more composition attempt. If that also fails → a fixed template for that case. This way the reply is always safe, even if less natural." The five templates cover every possible `action` combination (`reply`/`escalate` with or without a service request, and `clarify`), each worded to already pass all 4 guard checks (no dates, no forbidden words, includes the SR id when needed).

## An implementation decision not detailed in the source (documented)
**Detecting "a forbidden word depending on intent"** — the design phrases this as intent-dependent (POL-04 for cancellation, POL-06 for a damaged item), but in practice I chose to **check all 5 words always, for every intent**, not only per the relevant policy. Reasoning: none of these words (cancelled/approved/compensation/guaranteed refund/you'll get a replacement) is permitted under any of the 7 policies (POL-01..07) — they're always forbidden, whether the current intent is cancel, damaged_item, or anything else. A blanket check is simpler and stricter, and doesn't contradict any policy line. If testing (part 10) reveals a false-positive case, it will be documented as an improvement (part 10's "documented improvement" template). [Update: this is exactly what happened — see part 10, improvement #1: not the intent-based check, but a date-normalization bug in this same function, which produced a false positive on a genuinely correct date.]

**Date detection via regex** (`\d{1,2}\.\d{1,2}\.\d{2,4}` or ISO) is my own heuristic, not written in the source — reasonable coverage for the formats that appear in the data (`orders.json`, converted in part 1) and in spoken Hebrew, without building a full date parser (in keeping with the spirit of assignment line 127: "no extra credit for... a proliferation of components").

## How this satisfies the requirement
- Assignment, line 88 (preventing exposure of another customer's order) — an additional layer of defense on top of `order_service` (part 4): even if the model "leaks" a foreign order number into the reply, the Guard catches it.
- Design, line 106: "Even if the model errs, is injected, or fabricates, it cannot cause... information exposure. In the worst case the classification is wrong, and that's caught in testing" — the Guard is the direct implementation of that sentence for free-text content (the composed reply).
