# Part 7 — Orchestration (agent.py, run.py)

## What was built
- `src/agent.py` — a `handle(customer_id, message, today, context, simulate_outage, run_id)` function that wires all the components (parts 2–6) into a single flow and returns an `AgentResponse`.
- `run.py` — a CLI that calls `handle` and prints JSON.
- A small addition to `src/llm.py` from part 5: a `run_text` function (free text, not JSON) — needed because LLM #2 (composition) doesn't produce structured JSON the way LLM #1 (extraction) does.

## Why it was built this way (source of truth)

**The stage order in `handle()` is a direct translation of the flowchart** in the design, section 8 (lines 112–142): input → LLM#1 extraction → Pydantic validation → Order Service → (not found/unavailable → fixed reply) | (found and owned → Policy Engine → SR Tool + LLM#2 composition → Reply Guard → AgentResponse).

**Two nodes in the flowchart (N and F) bypass LLM#2 and the Guard entirely** — this isn't my own choice but an exact reading of the flowchart's arrows: "D -- not found/not owned --> N[reply: not in your account]" and "D -- unavailable --> F[escalate: technical failure]" (lines 124, 126) — neither arrow passes through E/H at all. So `NOT_FOUND_REPLY` and `OUTAGE_REPLY` are fixed text in code, not model output. The wording of `NOT_FOUND_REPLY` is an **almost exact quote** from the design itself, section 6, line 86: "I couldn't find an order with that number in your account" + a request to check the number.

**By contrast, the `clarify` case coming from `policy_engine`** (e.g. return+unknown, assignment case 5) **does** go through LLM#2 and the guard, because in the flowchart E (Policy Engine) always feeds both G and H, with no exception for clarify. This required synthesizing two parts of the same design doc (the table in section 11 vs. the diagram in section 8) — not written as one explicit sentence, but the direct conclusion from reading both together.

**The two clarify checks that stay fixed in code and never reach LLM#2** — "no order number" and "more than one order number" (table, lines 288–289) — because at this stage **there is no order object yet** to build a facts package from; this happens *before* D in the diagram, so technically it also cannot pass through E→H. The wording of these two questions is my own (not quoted from the source), but answers exactly the definition in the design, section 6, line 84: "State: a detail the customer can supply is missing → action: clarify → what the customer experiences: one, focused question."

**The service request is opened before the composition call** — the `create_request(...)` lines appear before `_compose_reply(...)` in `handle()`, exactly per the design, line 147: "The service request is opened before composition, so the SR number quoted in the reply is real."

**The first model never sees order data** — `run_structured(build_extraction_system(), user_text, Extraction)` receives only the customer's text (and `context`, if any), never `order`. Matches line 146: "The first model doesn't see order data at all."

**Rerun with context (A8)** — when `context` is present, it's appended to the text before sending to LLM#1, not managed as a live conversation. Matches A8 (line 75) and the design's own CLI example, line 502: `python run.py C-101 "not opened" --context "return:ORD-1003"`.

**`_facts_and_guardrails`** builds exactly the fields shown in the design's facts-package example (lines 328–334): `order_id`, `status`, dates, `service_request`, and an internal reason — fed into `build_reply_system` (must_say/must_not_say) built in part 5.

## Addition to llm.py: `run_text`
The design didn't define a separate function for composition (only "LLM #2: reply composition" in the diagram, line 132), but technically **this is a different kind of call** from `run_structured` — no JSON schema to enforce, just free text. I added `run_text` to `llm.py` on the same provider chain and the same `temperature=0` (lines 295, 305), retrying only on an empty output (there's no schema error to retry on).

## CLI (`run.py`)
The three flags (`--context`, `--simulate-outage`, `--today`) and the basic usage were copied from the design's run examples, section 21 (lines 500–504). The default for `--today` (`2026-09-22`) is the assignment's fixed reference date (line 38), overridable both via `.env` (`TODAY=`) and via the flag, as A2 requires (line 69).

## How this satisfies the requirement
- Assignment, line 90: "A runnable flow is required; a manual conversation with a model alone is not enough" — ✅ `run.py` is a complete end-to-end flow.
- Assignment, line 78: "Opening a service request can happen alongside it... e.g. opening a cancellation request and sending a reply confirming the request was received" — ✅ `sr_ref` is built before `_compose_reply` and injected as a fact into the reply.
