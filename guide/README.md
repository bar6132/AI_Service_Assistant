# Inside the Service: a listenable guide to the backend

An interactive guide to how the customer-service backend works and why. It teaches from the simplest function up to the AI flow, the backups, the guardrails, the tests and the scoring.

## Open it

Double-click [index.html](index.html). No server, no install, no network needed (fonts load from Google when online, system fonts otherwise).

Press the play button at the bottom to hear any chapter. Click the small play button next to any paragraph to start from there.

## What is inside

| Chapter | Teaches | Play with |
| --- | --- | --- |
| 0 [The big picture](md/00-big-picture.md) | The seven stations, model vs code | Cast of characters, message pipeline, build timeline |
| 1 [The data](md/01-data.md) | Why JSON files, where the data came from | Orders and policies browser |
| 2 [Data contracts](md/02-contracts.md) | Pydantic forms and validators | Form validator playground |
| 3 [Order numbers and grounding](md/03-order-ids.md) | The model finds, the code checks | Grounding lab |
| 4 [The policy engine](md/04-policy.md) | The decision table | Live decision table |
| 5 [Order lookup and ownership](md/05-orders-ownership.md) | Why not found equals not yours | Gate simulator |
| 6 [The service request database](md/06-database.md) | SQLite, idempotency, races | Database and two-writer race |
| 7 [The model layer and backups](md/07-llm-layer.md) | Provider chain, retries, repair, config | Provider failure game |
| 8 [Prompts and the AI flow](md/08-prompts-flow.md) | Two model jobs, why no tool-calling loop | Facts card builder |
| 9 [The reply guard](md/09-guard.md) | Deny-list, dates, fallback templates | Be the inspector |
| 10 [When things break](md/10-failures.md) | Honest failure handling | Break something on purpose |
| 11 [Automated tests](md/11-tests.md) | Fakes, what each file protects | Test map and mutation lab |
| 12 [Evals, scoring and what we found](md/12-evals.md) | Real runs, the review, what is missing | Ten cases and the eight high findings |
| 13 [Config and running it](md/13-config.md) | .env, TODAY, CLI | .env playground |
| 14 [What next, and a glossary](md/14-next.md) | Scaling, open work | Glossary |

The `md/` files are the source of truth. Each is plain markdown you can also read without the page.

## Edit it

1. Edit or add a file in `md/` (names sort in chapter order).
2. Run `python guide/build.py`. It writes `data/lessons.js` and `data/lessons.json`.
3. Refresh the page.

Markdown extras: `> [!eli5] text`, `[!path]`, `[!why]`, `[!honest]` callouts; `{{widget:name}}` places a widget; a `quiz` code block makes a quiz. See the header of [build.py](build.py).

## Voice

- **Now, zero setup:** the page uses your browser's speech voices. On Edge or Windows, pick a voice with "Natural" or "Online" in its name for the best quality. Speed and voice are in the player.
- **Optional local AI voice:** [tools/make_audio.py](tools/make_audio.py) renders every paragraph with Piper, a small offline neural text-to-speech model, into `audio/`. Then run `build.py`. The page plays those files and falls back to the browser voice for anything missing. This script was not run when the guide was created, because no voice model was downloaded yet.

## Trust but verify

The widgets run JavaScript ports of the real Python (`assets/logic.js`). To prove they agree:

```bash
cd matrix-ai-service
.venv\Scripts\python.exe ..\guide\tools\check_ports.py
```

It runs the Python originals and the ports on 523 cases (order ids, the full decision table, the reply guard, the fallback templates) and fails on any difference.

The mutation lab in chapter 11 shows real results: each bug was applied to a scratch copy of the code and the whole test suite was run.

## Things this guide found

Writing it surfaced three issues in the project:

1. A startup race in `src/service_requests.py` (concurrent first connections switching to WAL mode) made two tests flaky. **Fixed**, see chapter 6.
2. `test_free_text_context_is_rejected` used `pytest.raises(Exception)` and could not catch the bug it is named for. **Fixed**, see chapter 11.
3. There is no evaluation harness yet (design section 18), so language-understanding quality has not been measured at scale. **Open.**
