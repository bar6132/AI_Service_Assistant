---
title: Evals, scoring and what we found
station: Report card
role: guard
minutes: 11
---

## Tests ask "is the code right?". Evals ask "is the system good?"

> [!eli5] A spelling test checks if you know the rules. A report card checks how you do in real life. Unit tests are the spelling test. Evals are the report card, with the real model in the loop.

Automated tests use a fake model, so they cannot tell you whether Gemini understands a Hebrew complaint. For that we ran the real thing.

## The two numbers that matter, and why they fight

The design names two business scores.

- **Self-resolution**: the share of messages answered with a reply and no human.
- **Policy compliance**: the share with zero violations (leaking another customer's data, a forbidden promise, a wrong request). Target: 100 percent.

They pull against each other. The easy way to raise self-resolution is to let the system answer more: guess the product state, approve a borderline return, soften a refusal into a promise. Each of those risks a violation. The opposite, escalating everything, is safe but worthless.

> [!why] We decided compliance is a hard wall and self-resolution is what you maximize inside it. The clarify action is the tool that raises resolution without guessing: ask one focused question instead of making something up.

## Technical scores we track

- **Action accuracy**: did the action match the expected one.
- **Service request accuracy**: the right request opened, or none when none should open.
- **Schema validity**: share of model outputs that validated on the first try.
- **Latency**: p50 and p95, the typical and the slow case.
- **Cost**: tokens and money per message.

## The real run: ten cases against Gemini

What is fixed by code (action, request type, policy ids) was identical every run. What varies is the wording of the reply. A case passes when the code-decided parts are right and the guard accepted the wording.

{{widget:cases}}

All ten passed on the first run, and again on 30 September 2026 after the gap fixes. The re-run used an empty database so the request numbers could be compared.

> [!path] Two improvements came directly from these runs. First, case 5 fell into a generic fallback because the guard wrongly rejected a correct date written as 12.09.2026. We traced it, taught the guard to compare real dates, and re-ran. Second, case 1 never quoted the delivery date, because nothing told the model it must. We added a must-say line. A test that passes can still hide a poor answer, so we read the actual replies.

## The outside review: 29 findings

After the first version was done, an independent review compared the code to our own design document. 29 findings, 6 of them high severity. For every high one we first reproduced the bug locally, with fakes and no API key, then fixed it, then wrote the test.

{{widget:gaps}}

## What we did not do, said plainly

Ten cases, one provider, one run each, is wiring proof, not reliability proof. The design planned a proper evaluation lab (section 18): 15 to 20 rephrasings per case, injection attempts, N repeats per input, a matrix of models and prompt versions, and 20 percent of phrasings held back so we do not overfit the prompt to our own tests. It was marked optional and **not built**. There is no `eval/` folder yet.

Also not measured: token counts, systematic latency, Grok and the local server, and the cost per thousand messages beyond "free tier".

> [!honest] If someone asks "how accurate is it?", the truthful answer today is: all ten known cases pass, the policy parts are deterministic and unit-tested, and the language-understanding part has not been measured at scale.

## What a real eval harness would look like

1. A file of labelled messages: text, expected intent, expected action.
2. A runner that sends each message N times through `handle`.
3. Scores computed in code, with no model grading another model: intent accuracy, action accuracy, violations (target zero), first-try schema validity, fallback rate, latency percentiles, and stability (do all N runs agree).
4. A held-out slice used only for the final report.
5. Failures sorted by cause: prompt, schema, decision table or guard. Fix the right part, re-run everything.

## Check yourself

```quiz
Q: Why are unit tests not enough to judge the AI quality?
- They are too slow
* They use a fake model, so they say nothing about how the real model understands customers
- They test the wrong language
- They are not allowed
? Only runs with the real model show real understanding.

Q: Which is a hard wall and which is maximized?
* Policy compliance is the wall, self-resolution is maximized inside it
- Self-resolution is the wall
- Both are maximized equally
- Neither matters
? A single violation costs more than many escalations.

Q: Why hold back 20 percent of phrasings in the planned lab?
- To save time
* So we do not tune the prompt to our own test set and fool ourselves
- Because of cost
- The model needs rest
? Held-out data is the honest score.
```
