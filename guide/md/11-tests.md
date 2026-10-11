---
title: Automated tests
station: Test lab
role: code
minutes: 10
---

## Tests are a promise that keeps itself

> [!eli5] Imagine you build a toy robot. Every night a little helper presses every button and checks the robot still does the right thing. If you accidentally break the arm while fixing the leg, the helper tells you the next morning, not the customer. Our tests are that helper.

There are 131 tests in 7 files. On a normal run 129 pass and 2 are skipped on purpose (a clarifying question that also opens a request is impossible by design, so that combination is skipped).

None of them calls a real model or needs an API key. They run in about six seconds.

## The trick: fakes

How do you test a system that depends on an AI model, without the AI model? You replace the model with a **fake** function that returns exactly what you decide. Now you can test "what if the model invents an order number" by simply making the fake do that.

```py title="tests/test_agent.py"
def extraction(intent="cancel", order_ids=("ORD-1001",), ...):
    def fake(system, user, schema_model):
        return Extraction(intent=intent, order_ids=list(order_ids), ...)
    return fake

def test_model_order_id_not_in_text_is_never_acted_on(monkeypatch, temp_db):
    use(monkeypatch, extraction("delivery_delay", ["ORD-1002"]))
    r = handle("C-101", "איפה ORD-1006?", today=TODAY)
    assert r.action == "clarify" and r.order_id is None
    assert db_rows(temp_db) == []
```

The same idea is used for the database: every test gets its own empty temporary database (`temp_db` in `conftest.py`), so tests never see each other's rows. And for the model layer, `test_llm.py` starts a tiny fake HTTP server that can answer 503, 401 or broken JSON on demand.

> [!path] The path we took: at first there was one test file. The README promised pytest worked, but there was no pytest file, a gap between what we claimed and what existed. We wrote the policy tests first, then, after the outside review, one test per finding. Coverage went from 23 percent to 93 percent.

## What each file protects

{{widget:testmap}}

## Break the code, watch the test catch it

The best way to understand a test is to ask "what bug would this catch?" Pick a bug below and see which test would turn red.

{{widget:mutation}}

## The two kinds of test

- **Example tests.** One situation, one expected answer. Like day 14 is allowed.
- **Property or stress tests.** Hit the code hard and check a rule still holds. `test_concurrent_writers_never_collide` fires 200 writes from 8 threads and checks all 200 ids are different.

> [!honest] Writing this guide found two test problems, both now fixed. First, `test_free_text_context_is_rejected` used `pytest.raises(Exception)`, which passes for any crash at all. When we loosened the context pattern on purpose, nothing turned red. It now expects `ValidationError`, and we checked it turns red on that bug. Second, two concurrency tests failed about half the time with "database is locked". That was a real bug, not a bad test: see chapter 6. After the fix they passed twelve runs in a row.

## How to run them

```bash title="from matrix-ai-service/"
python -m pytest            # quiet
python -m pytest -v         # every test name
python -m pytest tests/test_policy_engine.py -v
```

Use `python -m pytest`, not bare `pytest`. On a machine with several Pythons the bare command can launch a different one that does not have your packages.

## Check yourself

```quiz
Q: How do we test "the model invented an order number" without a model?
- We ask Gemini to do it
* We replace the model call with a fake that returns exactly that
- We cannot test it
- We delete the check
? Fakes let a test create any model behaviour on demand.

Q: A test that passes sometimes and fails sometimes is called
- Perfect
- Coverage
* Flaky, and it usually points to a real race or timing problem
- Skipped
? Flaky tests are not noise. They are an uninvestigated bug report.
```
