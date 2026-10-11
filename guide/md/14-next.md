---
title: What next, and a glossary
station: Horizon
role: none
minutes: 7
---

## If this became a real service

> [!eli5] Right now our service is a food stall: one customer at a time, fast and tidy. A food hall serves many at once. Most of the kitchen stays the same. You mainly add more counters and a good queue.

The design document says what would change. In priority order:

1. Safe ids and WAL mode. **Done** in the gap round.
2. A shared rate limit toward the model provider. We already saw 503s from the free tier with just one user.
3. An HTTP layer and async calls, or a thread pool as a cheaper first step.
4. Structured logs with a request id on every line, so one request can be traced through a busy log.
5. A separate model gateway, only when there are several instances.
6. Durable workflows such as Temporal, only if one request turns into a long, multi-step agent.

**What would not change**: `handle()` keeps no state between calls, so more machines just work. Policy stays in code. Idempotency in the database stays.

> [!why] A good design survives growth by being easy to change in the right place. That is why restructuring folders was postponed: growth will tell us where the pain is. Pain signals are more intent types, more providers, real external systems, several entry points, or more people.

## The growth list we did not build

- A real evaluation lab with rephrasings, repeats and a held-out set.
- Pinned dependency versions and continuous integration.
- Filtering personal information before sending text to the provider.
- Handling general questions, several intents in one message, and a limit on clarifying questions.
- A history of events per request.
- Using the `asks_compensation` field, which is extracted but not yet used.

## Glossary

{{widget:glossary}}

## You made it

You can now trace one message from the customer's words to the stored record, and say why every step exists. The best next move is to open the demo page under `matrix-ai-service/progress/Demo/` and watch a real run. After that, build the evaluation lab.

```quiz
Q: Which part would you change first to serve many customers at once?
- The policy table
* The runtime layer: HTTP, async and rate limits, since the core logic is already stateless
- The data contracts
- The guard
? The brain is stateless. Scaling is mostly a deployment problem.
```
