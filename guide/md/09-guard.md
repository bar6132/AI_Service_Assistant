---
title: The reply guard
station: Inspector
role: guard
minutes: 9
---

## The last pair of eyes

> [!eli5] Before a letter goes in the mailbox, a careful grown-up reads it with a red pen. Any promise the shop cannot keep, any wrong date, any secret code word gets circled. If the letter has circles, the writer tries once more. If it still has circles, we send a safe pre-written letter instead.

`src/reply_guard.py` reads the model's draft and returns a list of problems. An empty list means it passed. It checks, in Hebrew and English:

- **Order numbers**: only the current order may be mentioned.
- **Dates**: every date must be one of the order's real dates, in any written format.
- **Commitment words**: cancelled, approved, refund, compensation, guaranteed, and their Hebrew forms.
- **Relative deadlines**: tomorrow, next week, within 3 days.
- **Money**: shekel signs, NIS, dollars, euros.
- **Internal terms**: POL-04, agent_handoff and similar.
- **Request numbers**: only the real one, and it must be present when a request was opened.

{{widget:guard}}

> [!path] The path we took, in two rounds. Round one had four checks copied from the design (order numbers, dates, five forbidden words, request number). Then real testing found a false alarm: the model wrote 12.09.2026, the facts said 2026-09-12, and the guard called a correct date wrong. We taught it to compare real dates. Round two came from the outside review: 18 of 20 unsafe phrasings slipped past the first guard. We widened it to the list above.

## Dates are the hard part

People write dates many ways: 2026-09-12, 12.09.2026, 12/09/2026, "12 בספטמבר", "September 12", "12th of September 2026". The guard finds all of them, turns each into a real date, and compares to the allowed ones. A reply that says "tomorrow" is also blocked, because it is a promise of a time.

## Retry with feedback

When the guard rejects a draft, we ask the model once more. But at temperature 0 the same prompt gives the same draft. So the second prompt includes the guard's complaint, for example "the previous draft was rejected because: it contains a date not in the facts. Rewrite without it."

If the second draft also fails, `fallback_reply` sends a fixed template for that situation, in the customer's language. Less natural, but always safe.

```py title="src/agent.py"
for attempt_num in range(1, 3):  # original attempt + one retry
    reply_text = run_text(system, prompt)
    violations = guard_check(reply_text, order["order_id"], allowed_dates, sr_id)
    if not violations:
        return reply_text
    prompt = facts_text + "...הטיוטה הקודמת נפסלה בגלל: " + "; ".join(violations)
return fallback_reply(decision.action, sr_id, language)
```

## The honest limit

The guard is a deny-list. It blocks what we thought of. It cannot be complete. A legitimate sentence like "we cannot promise compensation" is blocked because it contains the word compensation, and falls back to a template. That is the trade we chose: sometimes stiff, never unsafe. The main protection is still upstream: the model only ever sees a closed card of facts.

> [!why] Defense in depth. No single wall is perfect, so we stack them: the model has no data, the code decides, the card limits what can be said, the guard checks what was said, and a template catches the rest.

## Check yourself

```quiz
Q: The model writes "Your order will arrive tomorrow". What does the guard do?
- Passes it
* Flags a relative deadline, so the model retries with feedback
- Deletes the word
- Escalates
? Relative times are a promise. They are blocked in Hebrew and English.

Q: Why does the retry prompt include the violations?
- To annoy the model
* At temperature 0 an identical prompt would return an identical draft
- Because the SDK needs it
- To log them
? New information is the only way to get a different answer.
```
