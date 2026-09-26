# Part 9 — Gemini model choice + a security fix

## What was built
- `src/llm.py`: the `GEMINI_MODEL` default was changed to `gemini-3.1-flash-lite` (instead of `gemini-flash-lite-latest`, which doesn't actually exist).
- Security fix: a real API key that was accidentally pasted into `.env.example` was removed from there.

## The security fix (first, because urgent)
While filling in `.env`, the same key also got pasted into `.env.example`. `.env` is in `.gitignore` (part 8), but `.env.example` is **not** — it's a template file meant to be checked into version control. A real key there would be exposed on every commit/share of the project. Removed from `.env.example` back to empty; in `.env` it remains as planned (part 8, "keys only in .env, which is in .gitignore" — design line 358).

**Recommendation:** since the key was also exposed in plaintext outside `.env` at one point, rotating it in Google AI Studio is worth considering as a precaution.

## Choosing a Gemini model — not in the source docs, documented separately

**This is not a decision grounded in the two Docs files** — they only establish "Gemini Flash-Lite" as a category (design, lines 20, 301, 310), without naming a version. The choice between versions was made by checking Google's live documentation (aistudio.google.com/docs/models, ai.google.dev/gemini-api/docs/pricing and /models) on 2026-09-25, not from prior training knowledge — because the model list changes over time.

**What was checked:**

| Model | Status | Input price/1M | Output price/1M | Free tier |
|---|---|---|---|---|
| Gemini 3.1 Flash-Lite | Stable | $0.25 | $1.50 | yes |
| Gemini 3.5 Flash-Lite | Stable | $0.30 | $2.50 | yes |

**Why 3.1 Flash-Lite and not 3.5 Flash-Lite:** actually cheaper (despite the lower version number) — $0.25/$1.50 vs. $0.30/$2.50 per million tokens — and described in the docs as "Frontier-class performance rivaling larger models at a fraction of the cost," i.e. not just cheaper but more accurate relative to its size. Both versions have a free tier. For this task (Hebrew classification, resistance to prompt injection, exact JSON-schema compliance) — higher accuracy at a lower price is an unambiguous call.

**The exact API id** (`gemini-3.1-flash-lite`) was verified against `ai.google.dev/gemini-api/docs/models` — the generic alias I assumed in part 5 (`gemini-flash-lite-latest`) **doesn't actually exist**, and was fixed.

## How this satisfies the requirement
- Design, line 19: "Testers can run the solution with any of them [the providers]" — `.env` is currently set to `PROVIDERS=gemini` only, since that's the key available.
- Assignment, line 9: "No need for... a paid service" — Flash-Lite with a free tier allows running every test case at no cost.
