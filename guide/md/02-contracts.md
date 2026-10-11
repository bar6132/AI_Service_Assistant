---
title: Data contracts
station: Forms
role: code
minutes: 7
---

## Forms with boxes

> [!eli5] A contract is a paper form with boxes. The box for a phone number only accepts digits. If someone writes a poem in it, the form says no. We made forms for everything that moves through the system, so nothing odd gets in.

In `src/models.py` we use a library called Pydantic. You describe the shape of your data once, and Pydantic refuses anything that does not fit. There are five main shapes.

- `AgentInput`: what comes in. Customer id like C-101, a message of 1 to 2000 characters, and an optional context.
- `Extraction`: what LLM number one must return. Intent, order ids, product state, whether they ask for compensation, and language.
- `Order`: what an order record must look like before the policy engine may touch it.
- `ServiceRequestRef`: the type and id of a request we opened.
- `AgentResponse`: what we return. Always the same seven fields.

{{widget:contracts}}

> [!path] The path we took: the design document already described these shapes in detail, so we copied them almost one to one. The output fields match the assignment's output table exactly. No field added, none dropped.

## Allowed values are locked

`Intent` can only be one of six words: order_status, delivery_delay, cancel, return, damaged_item, other. `PolicyId` can only be POL-01 to POL-07. That means a policy id that does not exist cannot sneak into an answer, and a model that invents a seventh intent gets rejected.

## Rules that check more than one box

Some rules look at two boxes at once. These are called validators.

```py title="src/models.py"
class AgentResponse(BaseModel):
    ...
    @model_validator(mode="after")
    def consistency(self) -> "AgentResponse":
        if self.service_request is not None and self.order_id is None:
            raise ValueError("service_request requires order_id")
        if self.action == "clarify" and self.service_request is not None:
            raise ValueError("clarify must not open a service_request")
        return self
```

Read it aloud: a request needs an order, and asking a question never opens a request. That is a sentence from the design document turned into code.

The `Order` model has one more: a delivered order must have a delivered date. If a record breaks that, we do not guess. We escalate to a human.

## The context is a form too

When the system asks a clarifying question, the follow-up arrives with a context such as `return:ORD-1003`. We lock its shape with a pattern. Free text is not allowed there, so it cannot become a second sneaky channel into the model.

> [!why] Every free-text input is a door for tricks. We keep the number of doors at one: the customer message. Everything else is a form with boxes.

> [!honest] One thing the model cannot do: Pydantic guarantees the shape of the data, not that it is true. A perfectly shaped extraction can still name the wrong intent. That is why later stations verify and decide in code.

## Check yourself

```quiz
Q: What happens if the model returns an intent called "refund_please"?
- We use it anyway
* Validation fails, so we repair, retry or move to the next provider
- The policy engine guesses
- The reply guard fixes it
? Intent is a locked list of six values. Anything else is a validation error.

Q: Why is the clarify context locked to a pattern like return:ORD-1003?
- To make logs shorter
* So it is not a second free-text channel into the model
- Because Hebrew breaks it
- The CLI requires it
? Free text is where injection hides. A fixed pattern is rendered by code into a fixed sentence.
```
