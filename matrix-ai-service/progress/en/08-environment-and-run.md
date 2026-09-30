# Part 8 — Environment, dependencies, .env

## What was built
- `requirements.txt` — the exact dependencies from the design.
- `.env.example` — the environment-variable template.
- `.env` — the real file, with `PROVIDERS=gemini` and an empty `GEMINI_API_KEY=` for manual entry (only a Gemini key is available right now).
- `.gitignore` — excludes `.env` and temp files from version control.
- Dependencies installed (`pip install -r requirements.txt`).
- **Two code fixes** in files from parts 5+7 (see below) — discovered while wiring up the `.env`, not before.

## Why it was built this way (source of truth)

**The dependency list** was copied word-for-word from the design, section 21, line 494: "Python 3.11+, `pydantic`, `openai` (as an OpenAI-compatible client), `python-dotenv`, `pyyaml`, `pytest`. SQLite is built into Python." (Installed on Python 3.14, satisfying the minimum requirement.)

**The `.env.example` structure** was copied from the design, lines 511–520: `PROVIDERS`, `XAI_API_KEY`, `GEMINI_API_KEY`, `LOCAL_BASE_URL`, `TODAY`. I added `XAI_MODEL`/`GEMINI_MODEL` (empty) because they're environment variables created in part 5 for exact model names — not in the original design, marked with a comment in the file itself.

**The real `.env` with `PROVIDERS=gemini` only** (not `grok,gemini` as the design's default) — because only a Gemini key is available right now. This matches the flexibility the design itself claims, line 19: "Testers can run the solution with any of them" — a single-provider chain is a valid configuration of the same mechanism (`_provider_chain()` simply splits on commas; a one-item list works too).

**`.gitignore` includes `.env`** — per the explicit security requirement in the design, line 358: "Keys only in `.env`, which is in `.gitignore`."

## Two bugs found and fixed (full transparency)

While assembling the `.env` and checking how `run.py` actually loads it, I found two problems in code from earlier parts:

1. **Wrong import order in `run.py`** (part 7): `load_dotenv()` was called **after** `from src.agent import handle` — meaning the entire import chain (`agent → llm`) read environment variables *before* `.env` was even loaded. Practical effect: the API key from `.env` never reached the code. **Fix:** `load_dotenv()` moved to before the `src.agent` import line.

2. **`os.getenv(VAR, default)` doesn't guard against an empty string** in `src/llm.py`: if `.env` has `XAI_MODEL=` (empty, as it appears in the `.env.example` I wrote), `os.getenv` actually returns an empty string, **not** the default — because `getenv`'s default only applies when the variable doesn't exist at all, not when it's empty. This would silently send a request with `model=""`. **Fix:** switched to the `os.getenv(VAR) or default` pattern everywhere relevant, and turned `PROVIDER_CONFIG` from a dict built once at import time into `_provider_config()`, a function called on every use — so the config always reflects the current environment state regardless of import order.

Neither issue came from deviating from the design — they're my own implementation mistakes in parts 5 and 7, only surfaced once I actually tried running the `.env`-loading chain end to end.

## How this satisfies the requirement
- Assignment, line 114: "Short run instructions and workspace requirements, without passwords and keys" — `.env.example` with no real values, `requirements.txt` to reproduce the environment.

## Update — gap-closure round (part 13)

- `.env.example`: `PROVIDERS=gemini` (tested), comments stating grok and local are supported but untested, and an explanation of `TODAY` — without it, the current date is used.
- `requirements.txt`: added `tzdata` on Windows so `Asia/Jerusalem` works.
