---
title: The model layer and backups
station: Model gateway
role: model
minutes: 11
---

## One plug, many models

> [!eli5] Imagine one wall socket that fits every lamp. You can swap lamps without rewiring the house. Our model layer is that socket. Gemini, Grok or a model on your own computer all plug in the same way.

`src/llm.py` talks to every provider through one OpenAI-compatible client. The three supported providers are `local` (a server on your machine, for example llama.cpp), `grok` and `gemini`. Switching is a setting in the environment file, not a code change.

> [!path] The path we took: the design said all providers share one interface. We wrote `_provider_config` to give each one a base url, a key and a model name. Only Gemini was ever tested for real, so the default chain is just `gemini`. Grok and the local server are supported in code but untested, and we say so in the README.

## Choosing the Gemini model

The design only said "a Flash-Lite class model". We did not trust memory for the exact name. We checked the live Google docs on 25 September 2026 and compared two candidates.

| Model | Input per million tokens | Output per million tokens |
| --- | --- | --- |
| Gemini 3.1 Flash-Lite | $0.25 | $1.50 |
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 |

3.1 was cheaper, rated well for its size, and has a free tier. We also found that the alias we first guessed, `gemini-flash-lite-latest`, does not exist. We fixed it to `gemini-3.1-flash-lite`.

## Two ways to call the model

- `run_structured`: asks for JSON that matches a schema. Used by LLM number one. The reply is validated by Pydantic right away.
- `run_text`: asks for a plain written answer. Used by LLM number two.

Both use `temperature=0`, which tells the model to be as consistent as possible.

## The backup ladder

This is the part that makes the service survive bad days. Each provider gets at most two calls. Then we move on.

{{widget:providers}}

The rules, in plain words:

- **The answer does not match the schema** (bad JSON, wrong field): try once more with a repair note added: "your last output did not match the schema, return valid JSON only".
- **A hiccup on the network** (timeout, rate limit 429, server error 5xx): wait one second, try once more.
- **A permanent error** (wrong key 401, bad request 400): do not retry. Move straight to the next provider.
- **Every provider failed**: raise `AllProvidersFailed`. The orchestrator turns that into a safe escalation.

```py title="src/llm.py"
def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False
```

## A hidden retry we turned off

The OpenAI client library secretly retries on its own. So one "attempt" in our logs could really be three network calls. That is what review finding G-07 caught. We set `max_retries=0`, so our chain is the only retry policy and the worst case is easy to calculate: two calls times the timeout, plus one second.

## Fail fast on bad settings

Before any customer message is handled, `run.py` calls `validate_config()`. A provider name that does not exist (say `groq`) stops the program with a clear error, and a provider without a key is skipped. Before, a typo would have crashed in the middle of a customer request.

> [!why] Silent failure is the worst failure. If the config is wrong we want to hear about it at startup, loudly, not discover at midnight that every customer is being escalated.

## Live proof

In the re-run after the gap fixes, two of the real Gemini calls got a 503 from the free tier. The one-retry rule resolved both, and the log showed it: attempt one transport error, attempt two ok.

## Check yourself

```quiz
Q: Gemini returns broken JSON. What happens first?
- We switch provider immediately
* One repair attempt on the same provider, with a note about the schema
- We escalate to a human
- We ignore the field
? A schema error is the model's mistake, so we tell it what was wrong and try once more.

Q: Gemini answers 401 (bad key). What happens?
* No retry. We go to the next provider
- Retry three times
- Wait one second and retry
- Crash
? A permanent error will not fix itself, so retrying wastes time.

Q: Why set max_retries=0 on the client?
- To save money
* So hidden library retries do not multiply our attempts and our chain is the only policy
- To go faster
- It is required by Gemini
? Otherwise one attempt could be three calls and the timing math would be wrong.
```
