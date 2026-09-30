# Part 12 — Unit tests (tests/test_policy_engine.py)

## What was built
`tests/test_policy_engine.py` — 14 `pytest` tests for `policy_engine.decide()`, no model involved (at the time of writing; 38 today — see the update at the end).

## Why this was built now (found while writing the README)
The project structure in the design (section 9, line 197) planned `tests/test_policy_engine.py` from the start: "unit tests for code only, no model." In practice, part 10 verified the 14-day boundary using a one-off `python -c` script in the terminal — it gave the correct result, but left no permanent test file in the project. While writing the README and seeing it promise `pytest` as the test command, that claim turned out to be false — no test file existed, `pytest` would have reported "no tests ran." That's a gap between what was presented and what actually existed, now fixed.

## What's covered
Every row of the decision table (design, lines 273–289): both order_status/delivery_delay paths, all three cancel states (processing/shipped/delivered), all five return paths (not yet delivered, unknown→clarify, unopened within window, opened, outside window), damaged_item, and an uncovered intent (POL-07). Includes the two cases already manually verified in part 10: the day-14 boundary (inclusive, `reply`+`return`) vs. day 15 (`escalate`).

## How this satisfies the requirement
- The README now promises `pytest`, which actually runs and passes — not an empty promise.

**Update (part 13):** this file grew to 38 tests (every status outside the policy → escalate), and tests for the guard, the orchestrator, the database and the model layer were added next to it — 129 passing tests in total. Coverage went from 23% to 93%.
- Design, line 197 — the file planned from the start, completed instead of staying a silent gap.
