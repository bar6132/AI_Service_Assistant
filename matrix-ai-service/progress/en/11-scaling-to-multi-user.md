# Part 12 — If this hadn't been a single-shot CLI: what changes for concurrent multi-client/multi-agent use, and why

**Context:** the entire solution (parts 1–11) was built exactly per the assignment's own definition — "a runnable flow is required" (`Docs/AIEngineerTest.md`, line 90), one `run.py` invocation per request, no requirement for a server, the cloud, or a paid service (line 9). This document is a **declared thought experiment**, not an actual change: what would change, and why, if the solution had to serve several clients (humans) or several other AI agents calling it concurrently, instead of one serial call.

This directly continues the discussion in part 11 (async vs. durable checkpointing) — here it's broken down per code component.

## Change table

| Component | Today (single-shot CLI) | What changes for a concurrent multi-user service | Why |
|---|---|---|---|
| **Entry point** | `run.py` — one Python process, one input, one output, then exits | An HTTP service (e.g. FastAPI/uvicorn) accepting concurrent requests | Several clients/agents need to reach one "brain" at the same time, not in sequence |
| **Execution model** | Synchronous `def handle(...)`, blocks until the API responds | `async def handle(...)` + `openai.AsyncOpenAI` throughout `llm.py` | Calls to Gemini are I/O-bound (waiting on the network); blocking-synchronous means one client delays everyone else. **Important: this is not a hard prerequisite** — a thread pool over the existing synchronous code also works, since the GIL doesn't block on I/O waits. Async is the more efficient version at large scale, not a gating condition |
| **Service-request id generation** (`service_requests.py`) | `_next_id()`: `SELECT COUNT(*)` then `INSERT` — a race condition under concurrent writes (already documented as a limitation in part 4) | Rely on SQLite's own `INTEGER PRIMARY KEY AUTOINCREMENT`, or `INSERT ... ON CONFLICT` with a retry, so the id is generated atomically inside the transaction | Two concurrent requests today can compute the same `COUNT` and get the same id — this is **the first and most urgent fix**, before any other change, because it breaks correctness, not just performance |
| **SQLite** | A single file, default `journal_mode` (rollback journal) — locks the whole file for writing | At minimum `PRAGMA journal_mode=WAL`; at higher load — move to a real multi-writer database (Postgres) | A rollback journal blocks concurrent writers against each other; WAL allows one-reader/one-writer concurrently without locking; at higher throughput SQLite itself becomes the bottleneck |
| **`order_service.py`** | `_load_orders()` reads the entire `orders.json` from disk on every call — fine for 6 records | Index-based lookup in a real database (or at least in-memory caching), not a full file scan per request | "Simulates an API" (assignment, line 84) is enough for a prototype; a real catalog with many orders and concurrent requests needs a real lookup layer, not repeated file reads |
| **Provider-side rate limiting** | No internal rate limiting at all — every request sends calls directly to Gemini | A shared token-bucket / queue that limits the outbound request rate for the whole process, not just per-request retries | We saw live (part 11) that even single-user load gets intermittent `503`s from the free tier; multiple clients multiply the request rate and get closer to the provider's rate limit (429). A shared limiter gives a predictable queue/backoff instead of cascading failures across all clients |
| **Idempotency key** | `(order_id, type, status='open')` — a **business-level** key: "don't open the same request twice for the same order" | Also add a **request-level** idempotency key (e.g. an `Idempotency-Key` HTTP header, based on `run_id`+step) | Two different kinds of duplication: business duplication (the customer asks again) vs. technical duplication (the same HTTP call retried because of a network/client-level retry). The existing key already correctly solves the first; the second is complementary, not redundant |
| **Observability** | Basic logging to stderr (part 11), one process, no overlapping requests to confuse | Structured logs (JSON lines) with a `request_id`/`run_id` on every line, to reconstruct a single request out of an interleaved log stream from several concurrent requests | `agent.py` already generates an internal `run_id` (part 7) — it's just not threaded into the logs themselves yet, because a single CLI call has nothing to confuse. In a concurrent server this becomes critical, not a nice-to-have |
| **Access by other AI agents (not just human customers)** | The only trust boundary is `customer_id` — trusted because the calling system (the service channel) already authenticated the human customer | A separate authentication layer **for the calling service itself** (an API key/JWT per calling agent), separate from `customer_id` | If the callers are other AI agents and not just one trusted service channel, you need to know *who* is calling, not just *on behalf of which customer* — two different authentication layers, not one |
| **Model gateway** | `llm.py` already implements this in-process: `_provider_config`/`_provider_chain`, one unified OpenAI-compatible interface, automatic provider fallback | Extract into a separate Gateway service (LiteLLM, etc.) **only** once there are multiple instances of the service that need to share a central rate-limit/budget | With a single instance there's no benefit to a separate gateway — it's overhead with no value. It becomes relevant once several processes/machines need to "know about" each other |
| **Deployment** | A single Python process, exits after one call | An ASGI application (uvicorn/gunicorn) with several workers; `agent.py` is already stateless, so there's no state to share between workers; behind a load balancer | Statelessness already exists in practice (a strength of the current architecture) — horizontal scaling doesn't require a logic change, only a runtime layer |
| **Durable checkpointing (e.g. Temporal)** | Doesn't exist, not needed | **Still not needed even at multi-client scale** — only if a single request turns into a long agent loop (minutes, several tools, autonomous planning), against principle #1 (deterministic flow) already adopted | An explicit trigger condition: if a future feature runs a multi-step autonomous agent for a single request — **then** revisit this. Right now every request is short and idempotent, there's nothing to preserve |

## What does **not** change (and stays true even at large scale)

- **`agent.py` stays stateless** — the `handle()` function doesn't hold state between calls; horizontal scaling (more processes/machines) doesn't require a change to the logic itself, only to the deployment layer.
- **Read/write separation** (`order_service.py` vs. `service_requests.py`) — already matches the least-privilege principle, no change needed.
- **Policy enforcement in code, not in the model** (`policy_engine.py`) — even more correct at multi-client scale: consistent enforcement across every request, with no dependence on model behavior that could vary between calls.
- **Existing idempotency in `create_request`** — this is exactly why durable checkpointing isn't needed at all, even under load.

## Priority summary (if and when actually required)

1. Fix the race condition in `_next_id()` — **breaks correctness**, not just performance.
2. `WAL mode` in SQLite.
3. A shared rate limit against the provider.
4. An HTTP layer + async (or a thread pool as a cheaper intermediate step).
5. Structured observability with a `request_id`.
6. A separate gateway — only once there are multiple instances.
7. Durable checkpointing — only if the architecture itself changes into a long agent loop.

## How this satisfies the requirement
Not an assignment requirement — a thought document produced at the user's request, to show the current architecture is **aware** of its limits under load, not simply "untested."