# Part 13 — Closing gaps after a code review

## What was built
A round of fixes following an external gap-analysis report on the repository: 29 findings, 6 of them high severity. Every high-severity finding was reproduced locally before it was fixed. Every finding that contradicts the design document itself was fixed (Tier 1), the documentation was synchronized (Tier 2), and the rest were documented as known limitations (Tier 3).

## How the report was verified
The report's experiments were re-run with no API key: fake model functions, a temporary database, and a local HTTP server that returns 503. Every HIGH finding reproduced:

| Finding | What reproduced |
|---|---|
| G-01 | The message said ORD-1006, the model returned ORD-1002 (same customer) → a real request was opened on ORD-1002 |
| G-02 | Order-service outage → reply "your request was forwarded", zero rows in the DB |
| G-03 | Unwritable database → unhandled `OperationalError` |
| G-04 | Two writers got the same id `SR-000001` |
| G-05 | 7 of 8 unsafe phrasings passed the guard (English, `יבוטל`, `26/09/2026`, `מחר`, `POL-05`) |
| G-06 | A cancelled order was told "already delivered"; a missing date → crash |
| G-07 | 3 HTTP calls per "attempt" (hidden SDK retries) |
| G-08 | `PROVIDERS=groq` → unhandled `ValueError` |

## Why it was built this way (SOT)
The rule for choosing: fix everything that contradicts the design document itself, because that is a contradiction the repository makes about itself, and any reviewer who reads `Docs/` can find it. Anything the assignment doesn't require and that adds components was not built (assignment, line 127: "no extra credit for... a proliferation of components").

**Tier 1 — code fixes:**

| Finding | Fix | Source of truth |
|---|---|---|
| G-01 | New `src/order_ids.py`. The code normalizes the order ids the model proposed, de-duplicates them, and keeps only an id actually written in the text or the context | Design, section 7, line 97: "the model finds, the code verifies" |
| G-02 | Every escalate opens an `agent_handoff`, including technical failures. If that write fails, the reply doesn't claim the request was forwarded | A6, line 74 |
| G-03 | A failed service-request write → escalate without a request number, instead of a traceback | Design, section 16, line 384 |
| G-04 | DB-generated id (`AUTOINCREMENT`), a partial unique index on open requests, WAL + busy_timeout | Design, line 266 (idempotency) |
| G-05 | Guard in Hebrew and English: inflections, every date format, relative deadlines, currency, internal codes, foreign order/request numbers | Design, section 14, lines 341–346 |
| G-06 | An `Order` model validates the record after the ownership check; a status outside the policy → escalate, POL-07 | Assignment, POL-07 (line 35); design, line 272 |
| G-07 | `max_retries=0`; the chain is the only retry policy — one retry, and only on a transient error | Design, line 309 |
| G-08/09 | An unknown or keyless provider → a clear `ConfigError` at startup; the default is `PROVIDERS=gemini`, the tested provider | Design, lines 309 and 515 |
| G-10 | The second composition attempt receives the list of violations | Design, line 346 |
| G-11 | `--today` with no value → the current date in Asia/Jerusalem; `TODAY=2026-09-22` in `.env.example` stays for tests | A2, line 70 |
| G-14 | CLI errors are returned as JSON, exit code 2 | Design, section 21 |
| G-15 | Fixed replies and fallback templates in Hebrew and English | A5, line 73 |
| G-17 | LLM #2 receives `decision_context` without policy codes, not `reason` | Design, line 104: "reason — staff only" |
| G-20 | `--context` is structured (`intent:ORD-XXXX`) and rendered by code into a fixed sentence | A8, line 76 |

**Tier 2 — documentation:** the design document was updated in place, line for line (no lines moved, since every doc cites it by line number): status "final", the results tables (17.1, 19, 20) filled in, the "(להשלים)" row in section 23 replaced, and every description the code no longer matches corrected. New limitations were appended at the end of section 24. The numbering of parts 11–12 was fixed, the README was aligned with the code (providers, tests, date), and every changed part got an "Update" section.

**Tier 3 — documented, not built** (design, section 24): the guard stays a deny-list; no statistical evaluation battery (`eval/`); Grok and the local server untested; `run_id` not in the logs and tokens not measured; general questions, multi-intent messages and a clarify cap; `asks_compensation` unused; no event history per request; PII filtering; pinned versions and CI.

## How it was tested
- **Automated tests:** 129 pass and 2 are skipped on purpose (clarify with a request number is impossible), all without a real model. Coverage went from 23% to 93%. One test per finding: `test_agent.py` (grounding, handoffs, DB failure, language, guard feedback), `test_reply_guard.py` (every phrasing from the report, templates pass the guard, the part 10 date regression), `test_service_requests.py` (200 concurrent writes, 40 attempts at the same request), `test_llm.py` (fake server: 503, 401, schema error, configuration), `test_order_service.py`, `test_order_ids.py`.
- **Live re-run (2026-09-30)** of all 10 assignment cases against Gemini, on an empty database: all passed (details in part 10). Three observations from the run:
  - Cases 1 and 10 got a 503 from the free tier on the first attempt. The new retry resolved both, and this time it shows in the log.
  - Case 4's reply no longer contains "(POL-04)", which leaked in the first run.
  - Case 10 now opens a handoff record (`SR-000006`) instead of claiming "forwarded" with no record.

## How this satisfies the requirement
- Assignment, line 88: "Preventing exposure or action on another customer's order" — grounding also closes action on the *wrong* order of the same customer.
- Assignment, line 87: "Handling at least one failure" — every failure path is now handled according to the design's failure table (section 16), and tested.
- Assignment, line 110: "Document one improvement from testing" — this round is another improvement of the same kind: finding → reproduction → fix → re-verification.
