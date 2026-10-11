---
title: Config, environment and running it
station: Control panel
role: code
minutes: 7
---

## Settings live outside the code

> [!eli5] A music player has a volume knob on the outside. You do not open the player and rewire it to make it louder. Our knobs are in a file called `.env`.

The `.env` file holds settings and secrets: which providers to use, the API keys, the reference date. The code reads them when it starts. The `.env.example` file is a copy with the values left blank, safe to share.

```text title=".env.example"
PROVIDERS=gemini
GEMINI_API_KEY=
XAI_API_KEY=
LOCAL_BASE_URL=http://localhost:8080/v1
TODAY=2026-09-22
XAI_MODEL=
GEMINI_MODEL=
```

{{widget:env}}

## Why `TODAY` exists

The tests must give the same answer on any day. If "is this within 14 days" used the real clock, a test that passed in September would fail in October. So the reference date is a setting: `TODAY=2026-09-22` or the flag `--today`. If neither is set, the code uses the current date in Asia/Jerusalem.

## The key rule: secrets never get committed

`.env` is in `.gitignore`, so git never uploads it. Our own history has a lesson here: while filling in the settings, a real API key was pasted into `.env.example` by mistake. That file is meant to be shared, so the key would have been published. We caught it, removed it, and recommended rotating the key.

> [!path] The path we took, with two real bugs found while wiring the settings. Bug one: `run.py` loaded the `.env` file after it imported the agent, so the agent read empty settings and the key never arrived. Fix: load the file first. Bug two: `os.getenv("X", "default")` returns an empty string, not the default, when the file says `X=`. The model name became empty. Fix: use `os.getenv("X") or "default"`.

## Running it

```bash title="from matrix-ai-service/"
python run.py C-101 "אני רוצה לבטל את הזמנה ORD-1001."
python run.py C-101 "לא נפתח" --context "return:ORD-1003"
python run.py C-101 "..." --simulate-outage
python run.py C-101 "..." -v
python run.py C-101 "..." --today 2026-09-22
python run.py C-101 "..." --pretty
```

- `--context` carries the answer to a clarifying question into a fresh run.
- `--simulate-outage` pretends the order service is down.
- `-v` prints logs (provider, milliseconds, guard decisions) to stderr. The normal output on stdout stays pure JSON.
- `--pretty` shows a readable version for the terminal, with Hebrew ordered correctly using a small library called python-bidi.

Errors also come back as JSON, with exit code 2, never as a scary traceback.

## What gets logged, and what does not

Logs keep identifiers and timings, such as provider, model, attempt and outcome. They do not keep the customer's message text. A log file is a copy of data in another place, so we keep it boring.

> [!why] A CLI whose output is always one JSON object can be called by another program. That is the same contract a future web service would keep.

## Check yourself

```quiz
Q: Why is TODAY a setting?
- Python has no clock
* Tests that depend on the date must give the same answer on any day
- To confuse the model
- Gemini needs it
? Reproducibility. The same date gives the same decisions.

Q: What does XAI_MODEL= with an empty value do with os.getenv("XAI_MODEL", "grok-4-fast")?
- Uses grok-4-fast
* Returns an empty string, which would send a request with no model name
- Crashes
- Uses the local model
? getenv's default only applies when the variable is missing, not when it is empty. We use "or" instead.
```
