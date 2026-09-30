# Part 2 — Data contracts (models.py)

## What was built
`src/models.py` with 5 Pydantic classes: `AgentInput`, `Extraction`, `ServiceRequestRef`, `AgentResponse`, and the `PolicyId` constant.

## Why it was built this way (source of truth)

**The structure was copied almost 1:1** from the design doc, section 10 (`Docs/AI_Service_Assistant_Design.md`, lines 201–266) — that section was already defined precisely for this purpose, so there was no room to guess.

**Output fields (`AgentResponse`)** map one-to-one to the table in the assignment (`Docs/AIEngineerTest.md`, lines 68–76): `intent`, `action` (with the exact 3 values `reply`/`clarify`/`escalate`, line 71), `reply`, `order_id`, `source_ids`, `service_request`, `reason`. No field was added and none was dropped.

**`PolicyId`** as a Literal of the 7 values POL-01..POL-07 — based on the assignment's policy table (lines 27–35), the exact same 7 ids already stored in `data/policies.json` in part 1. This way `source_ids` can never point to a policy that doesn't exist.

**Order-id format validation (`ORDER_ID_PATTERN = ORD-\d{4}`)** is enforced in code (Pydantic), not trusted to the model — this is exactly the split defined in the design, section 7, line 96: "Extracting the order number — model, followed by regex verification in code: the model finds it, the code confirms the `ORD-\d{4}` format." Applied in two places: filtering `Extraction.order_ids` (what the model extracted from the text) and the `AgentResponse.order_id` field (the final result).

**The `consistency` validator** implements the rule written in the design, line 261, directly: "A service request requires an order_id; clarify does not open a request" — both conditions in the `model_validator` are a literal translation of that sentence.

## How this satisfies the requirement
- Assignment, line 66: "The prototype will return JSON including at least..." — the schema guarantees the output always contains all required fields in the correct format.
- Assignment, line 86: "Validating the structured output" — Pydantic validation (`ValidationError` on failure) is the validation mechanism itself; used in the failure-handling part (a later part).

## Update — gap-closure round (part 13)

- `Extraction.order_ids` is now normalized (`ord-1001` / `ORD 1001` → `ORD-1001`) and de-duplicated, instead of dropping anything that isn't an exact match.
- `AgentInput.context` is structured: `intent:ORD-XXXX`, up to 40 characters — not a second free-text channel into the model (design, A8, line 76).
- New `Order` model: an order record must have valid dates, and `delivered` requires a delivery date. An invalid record is stopped before the policy engine (design, line 272).
- `Decision.action` and `service_request_type` are typed as `Literal`, like `AgentResponse`.
