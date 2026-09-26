# Part 1 — Data files (orders.json, policies.json)

## What was built
Two JSON files under `data/`:

- `orders.json` — the 6 test orders.
- `policies.json` — policies POL-01 through POL-07.

## Why it was built this way (source of truth)

**The order data** was copied word-for-word from the table in `Docs/AIEngineerTest.md` (lines 40–47): order number, customer id, status, estimated delivery, delivery date — exactly as they appear there, with nothing added or guessed.

**One documented change:** dates were converted from the `DD.MM.YYYY` format used in the assignment to ISO `YYYY-MM-DD`, so the code can compare dates without extra parsing. This matches assumption A2 in the design doc (`Docs/AI_Service_Assistant_Design.md`, line 69): "Timezone: Asia/Jerusalem. The reference date is passed as a parameter (`--today 2026-09-22`)" — i.e. dates in code are always ISO.

**Policies POL-01..07** were copied word-for-word from the table in `Docs/AIEngineerTest.md` (lines 27–35). The assignment states explicitly (line 25): "These are the only approved policy sources for this assignment. Do not supplement policy from external sources" — so nothing was added, rephrased, or interpreted at this stage. The exact wording was preserved so that `source_ids` in the output point to real, checkable policy.

## How this satisfies the requirement
- Assignment, line 49: "Data may be kept in a file or a local structure" — ✅ local JSON file.
- Design, line 165: `data/orders.json` and `data/policies.json` as planned in the project structure (section 9) — ✅ matches.
