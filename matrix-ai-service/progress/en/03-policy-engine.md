# Part 3 — Policy engine (policy_engine.py)

## What was built
`src/policy_engine.py`: a `decide(intent, order, product_state, today)` function that returns a `Decision` (action, service-request type, source_ids, reason). This is the **decision table in code** — the heart of the solution.

## Why it was built this way (source of truth)

**Every line in the function is a direct translation** of the decision table in the design doc, section 11 (`Docs/AI_Service_Assistant_Design.md`, lines 273–289). No decision row was added that isn't there, and none was dropped (except two rows left out on purpose — see "What's not in here" below).

**Why this is in code and not the model** — this is exactly the decision recorded in the design, section 7, line 102: "`action`, `service_request`, and `source_ids` — code (decision table) — a business decision that must be consistent and auditable." And line 101: "Computing dates, delays, and the 14-day window — code — precise arithmetic. Models get dates wrong" — so `_eta_passed_not_delivered` and `_within_return_window` are pure Python date math, not something asked of the model.

**The 14-day return window is inclusive** (`today <= delivered + timedelta(days=14)`) — per assumption A3 in the design (line 70): "`today ≤ delivered + 14 days` (including day 14). Delivered 12.09 → day 10 → within window. Delivered 01.09 → day 21 → outside window." Using `<=` and not `<` is precisely to include day 14, as stated explicitly there.

**The `reason` field** is worded in code, not by the model, because line 103 of the design states: "The `reason` field for the team — code — the explanation follows from the rule that fired, so it's trustworthy." Every `reason` string here quotes the policy id that triggered it, so the team can audit the decision.

**Assignment case 6 example** (ORD-1004, delivered 01.09, "not opened", reference date 22.09.2026): `delivered_at=2026-09-01`, day 21 from delivery → `_within_return_window` returns `False` → `escalate` + `agent_handoff` + `POL-05` — exactly as required by the assignment (line 100) and planned in table 17.1, line 400.

## What's not in here (on purpose, not an oversight)
Two rows from the design's decision table (lines 288–289) are **not implemented in this file**:
- "any intent | no order number → clarify"
- "any intent | more than one order number → clarify"

Reason: `decide()` receives a single `order` that has already been located and confirmed to belong to the customer (matching the design, line 271: "Runs **only after** the order has been found and confirmed to belong to customer_id"). Checking how many order numbers were extracted from the text precedes this stage, so it will be implemented in `agent.py` (part 7, the orchestration) — not here, to keep the separation between "there is one valid order" and "what do we do with it." Documented here so it doesn't look like an accidental gap later.

## How this satisfies the requirement
- Assignment, line 82: "Using policy and order data to ground the result" — every `Decision` carries real `source_ids` from `policies.json`.
- Assignment, lines 30–35 (POL-02 through POL-07): every policy clause is mapped to at least one code rule.

## Update — gap-closure round (part 13)

- A status other than processing / shipped / delivered (e.g. cancelled, returned) → `escalate` + `agent_handoff`, POL-07 — for every intent. Before, cancelling an already-cancelled order got "the order was already delivered" (wrong). Basis: POL-07 in the assignment ("if a decision not covered by the policy is needed, escalate to an agent", line 35) and design, line 272.
- The cancel branch checks `delivered` explicitly; there is no more "everything else = delivered".
- 24 new tests (4 statuses × 6 intents) in `tests/test_policy_engine.py`.
