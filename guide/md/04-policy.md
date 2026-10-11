---
title: The policy engine
station: Kitchen rulebook
role: code
minutes: 9
---

## The heart of the system

> [!eli5] Think of a board game rulebook. If you roll a six, you move six spaces. No arguing, no feelings. The policy engine is that rulebook. Same situation in, same move out, every time.

`src/policy_engine.py` has one function: `decide(intent, order, product_state, today)`. It returns a `Decision` with four things: the action (reply, clarify or escalate), which type of service request to open if any, which policy ids were used, and a reason for the staff.

It only runs after the order was found and confirmed to belong to the customer.

> [!path] The path we took: the design document had a decision table, section 11. We translated it line by line. No row added, none dropped. Two rows (no order number, many order numbers) are handled earlier in the orchestrator, because they happen before there is any order to decide about.

## Play with the real rules

This is a faithful copy of the Python function running in your browser. Change the inputs and watch which row fires.

{{widget:policy}}

## Why code and not the model?

- Dates: "is today within 14 days of delivery" is arithmetic. Models make mistakes in date arithmetic. Python does not.
- Consistency: the same input must always give the same output, and a manager must be able to audit why.
- The reason field: because the code worded it from the rule that fired, staff can trust it.

```py title="src/policy_engine.py"
def _within_return_window(order: dict, today: date) -> bool:
    delivered = date.fromisoformat(order["delivered_at"])
    return today <= delivered + timedelta(days=RETURN_WINDOW_DAYS)
```

## One character that matters

Look at `<=` in the code above. The policy says the window includes day 14. With `<` a return on day 14 would be refused. Two tests pin this down: day 14 is allowed and day 15 escalates.

## Statuses the policy does not know

At first the code assumed an order is either processing, shipped, or "everything else is delivered". A review found that a cancelled order was told "already delivered", which is false. Now there is a list of known statuses. Anything else, like cancelled or on hold, escalates to a human under POL-07.

> [!honest] This is a good example of a quiet bug: the code ran fine, the answer looked polite, and it was wrong. Only an outside reviewer asking "what about cancelled orders?" found it. We added 24 tests: four statuses times six intents.

## Check yourself

```quiz
Q: A customer delivered on 2026-09-08 asks for a return on 2026-09-22 with an unopened product. What happens?
* Reply and open a return request, since day 14 is included
- Escalate, since two weeks passed
- Clarify
- Reply with no request
? 8 September plus 14 days is 22 September, and the check is today less than or equal to that.

Q: The order has status "cancelled" and the customer asks to cancel it. What happens?
- Say it was already delivered
- Open a cancellation
* Escalate to a human under POL-07
- Ask for the order number again
? The policy only covers processing, shipped and delivered. Anything else goes to a person.
```
