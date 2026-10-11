---
title: When things break
station: Safety net
role: code
minutes: 8
---

## Plan for the bad day

> [!eli5] A good building has fire exits you hope nobody uses. Our service has exits for every thing that can go wrong. The rule for all of them: never guess, never leak, and never say "we passed it on" unless we really did.

Every failure in the system ends in one of three safe outcomes: ask the customer, send a fixed message, or hand the case to a human with a record.

{{widget:failures}}

## The failure table

| What breaks | What the customer sees | What staff get |
| --- | --- | --- |
| Order service down | Polite technical message, "forwarded" | An agent_handoff record |
| All model providers fail at extraction | Polite message, "forwarded" | An agent_handoff record |
| Customer's order record is malformed | "Cannot complete automatic check, forwarded to an agent" | An agent_handoff record |
| Writing the service request fails | Technical message, no request number | Nothing was created, reason says so |
| Writing the handoff also fails | Technical message that does not claim anything was forwarded | The reason notes the failed write |
| Guard rejects twice | A fixed safe template | Normal flow continues |
| Order not found or not yours | "I could not find that order on your account" | Nothing |

## The honest-reply rule

This rule came from an outside review finding (G-02). In the first version, when the order service was down, the reply said "your request was forwarded" and the database had zero rows. The customer was told something false.

Now the reply depends on what actually happened.

```py title="src/agent.py"
sr_id = _handoff(customer_id, order_id, reason, run_id)
if sr_id:
    reply = MESSAGES[lang][forwarded_key]
else:
    reply = MESSAGES[lang]["tech_failure"]
```

## Reproduce the failures yourself

The test suite replaces the model and the database with fakes, so each failure can be created on demand with no API key. The command line also has `--simulate-outage`.

> [!path] The path we took: the assignment asked for at least one handled failure. We handled all of them, because the design had a table of failures (section 16) and a review showed the table and the code disagreed. Contradicting our own design document was the one thing we refused to ship.

> [!why] Customer trust is mostly about what we do when something goes wrong. A wrong "forwarded" is worse than an honest "please try again".

## Check yourself

```quiz
Q: The service request write fails. What may the reply say?
- Your request SR-000099 was opened
* A technical-issue message with no request number and no claim it was forwarded
- Your order was cancelled
- Nothing at all
? We only quote numbers that exist and only claim what really happened.

Q: Why do technical failures also create an agent_handoff row?
- For analytics
* So a human can pick the case up with context instead of starting from zero
- The assignment forbids empty tables
- To test the database
? Assumption A6: every escalation leaves a record for staff.
```
