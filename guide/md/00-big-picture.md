---
title: The big picture
station: Start
role: none
minutes: 8
---

## What did we build?

> [!eli5] Imagine a restaurant. A customer says something in their own words. A waiter listens and writes a neat ticket. The kitchen follows a strict rulebook and decides what happens. Then someone writes a polite note back to the customer, and an inspector checks that note before it leaves. That is our whole backend.

The real task: a customer of an online shop writes a free-text message, like "cancel order ORD-1001". Our service understands it, decides what is allowed, maybe opens a service request, and replies politely in Hebrew or English.

The one rule everything else follows: **the model understands and words things. The code decides and acts.**

{{widget:cast}}

## Why not just ask the AI to do everything?

An AI model is great with language and bad with rules. It can misread dates. It can be tricked by a sentence like "ignore the checks, I am the admin". It can promise a refund the shop never offered. A shop cannot allow any of that.

So we gave the model only two small jobs, and put every real decision in plain Python that always does the same thing.

> [!why] If the model is wrong, the worst case is a mislabeled request that a human reviews. It can never reveal someone else's order, because the code checks ownership before the model sees any order data.

## The seven stations

Every message walks the same road. Each station is one file you will visit in this guide.

1. **Understand** (model, LLM number one): turn free text into a small form. Intent, order number, product state, language.
2. **Verify** (code): the order number must really be written in the customer's text.
3. **Look up** (code): fetch the order, and only if it belongs to this customer.
4. **Decide** (code): the policy table picks reply, clarify or escalate.
5. **Record** (code and database): open a service request if one is needed.
6. **Write** (model, LLM number two): word a polite answer using only a small card of facts.
7. **Inspect** (code): the reply guard checks the answer. If it fails twice, a safe fixed template is sent.

{{widget:pipeline}}

> [!path] The path we took: we did not start by coding. We started from two documents, the assignment and our own design document. Every decision in this guide points back to a line in one of them. We built the boring, certain parts first (data, contracts, rules), the model layer in the middle, and the safety net last. Then we tested for real, found bugs, and worked through 29 findings from an outside review.

## How to use this guide

Each chapter has the same shape: a five-year-old explanation, the path we took, how it works, something to play with, the real code, and a short quiz. Press the speaker button at the bottom to hear any chapter read aloud.

## The thirteen parts, in the order we built them

{{widget:timeline}}

## Check yourself

```quiz
Q: Which of these does the AI model decide in our system?
- Whether an order can be cancelled
- Whether a return is inside the 14 day window
* What the customer is asking for, and how to word the reply
- Which service request to open
? The model understands text and writes words. Cancel, return window and request type are all decided by code.

Q: What is the worst thing a tricked model can do here?
- Show another customer's order
- Cancel an order by itself
* Label the request with the wrong intent, which a human then reviews
- Change the policy table
? The model never sees order data and has no power to act, so a trick can only produce a wrong label.
```
