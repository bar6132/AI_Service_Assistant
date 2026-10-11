---
title: The data
station: Pantry
role: db
minutes: 5
---

## Two small files

> [!eli5] Before a restaurant can cook, it needs a pantry and a recipe book. Our pantry is a list of six orders. Our recipe book is seven policy rules. Both are just text files.

We have two files in the data folder.

- `orders.json` has six test orders. Each has an order id, a customer id, a status, an estimated delivery date and a delivered date.
- `policies.json` has seven rules, named POL-01 to POL-07.

{{widget:data}}

> [!path] How we got the data: we did not invent it. The assignment document contained a table of six orders and a table of seven policies. We copied them word for word. The only change was the date format.

## Why plain JSON files?

The assignment said data may be kept in a file or a local structure. A JSON file is the simplest thing that works, anyone can open it, and git can show every change. A real database would add setup and hide the data from the reader, with no benefit for six rows.

> [!why] We kept the exact policy wording so that when the output says the answer came from POL-04, a person can open the file and check that POL-04 really says that.

## The one change: dates

The assignment wrote dates like 12.09.2026. We changed them to 2026-09-12, the ISO format. Code can compare ISO dates directly, and there is no confusion between day first and month first.

This tiny choice paid off later. Our reply guard had to learn that 12.09.2026 and 2026-09-12 are the same day, and a bug there was our first improvement from testing.

## What the seven policies say

- POL-01: only talk about orders that belong to the logged-in customer. The customer id comes from the system, never from the message text.
- POL-02: you may show the status and the estimated date, but the date is an estimate, not a promise.
- POL-03: if the estimate passed and it has not arrived, open a shipping inquiry. Do not promise a new date or compensation.
- POL-04: processing orders can get a cancellation request. Opening it does not mean it was cancelled. Shipped orders cannot be cancelled.
- POL-05: returns are allowed up to 14 days after delivery, including day 14, and only if the product is unopened.
- POL-06: a damaged product always goes to a human. No promise of refund or replacement.
- POL-07: never invent facts. Ask when something is missing. Escalate when the policy does not cover it.

## Check yourself

```quiz
Q: Why did we keep the policy wording exactly as given?
- It looked nicer
* So the policy ids in the output point to real, checkable rules
- The model needs the Hebrew text
- It saves disk space
? source_ids in the answer are only trustworthy if the policy text behind them was not reworded.

Q: Why convert 12.09.2026 into 2026-09-12?
* Code can compare ISO dates directly and there is no day/month confusion
- Python cannot read dots
- Because the assignment asked for it
- To make the file smaller
? ISO dates sort and compare correctly as plain values.
```
