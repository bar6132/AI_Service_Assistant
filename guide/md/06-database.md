---
title: The service request database
station: Records
role: db
minutes: 8
---

## A notebook that never repeats a number

> [!eli5] When you take a ticket at a bakery, the machine gives you the next number. Two people grabbing at the same time still get different numbers, because the machine hands them out, not the people. Our database is that machine.

When the policy engine says "open a cancellation request", `create_request` in `src/service_requests.py` writes one row into a SQLite database and returns an id like `SR-000002`. No real cancellation or refund happens anywhere. The only real action in the whole system is this one write.

## Why SQLite?

The assignment allowed a file, a local database or a tool. SQLite is built into Python, needs no server, and gives us real guarantees that a text file would not: atomic writes, unique constraints and safe concurrent access.

> [!path] The path we took, in two versions. Version one computed the next id as COUNT(*) plus one. That is fine for one person at a time. An outside review showed that two writers at once both counted the same number and one crashed. Version two lets the database hand out the number.

## Three guarantees, all enforced by the database

1. **Unique ids.** `seq INTEGER PRIMARY KEY AUTOINCREMENT`. SQLite assigns the number inside the insert. We show it as `SR-` plus six digits.
2. **No duplicates.** A partial unique index on `(order_id, type) WHERE status = 'open'`. Two open cancellations for the same order cannot exist. A second attempt is ignored, and we return the existing id.
3. **Safe sharing.** WAL mode and a busy timeout let readers and writers work at the same time without locking the whole file.

{{widget:database}}

```py title="src/service_requests.py"
cur = conn.execute(
    "INSERT OR IGNORE INTO service_requests "
    "(created_at, customer_id, order_id, type, status, summary, source_ids, run_id) "
    "VALUES (datetime('now'), ?, ?, ?, 'open', ?, ?, ?)",
    (customer_id, order_id, type_, summary, ",".join(source_ids), run_id),
)
if cur.rowcount == 1:
    return format_id(cur.lastrowid)
```

## Idempotent means safe to repeat

If the customer sends the same cancellation twice, they get the same `SR-000002` back, not a second record. The word for this is idempotent. We checked it live: rerunning case 2 returned `SR-000001` again.

The old way, "check if it exists, then insert", has a gap between the check and the insert where another writer can slip in. A database rule has no gap.

## Every escalation leaves a note

When the system hands a case to a human, it writes an `agent_handoff` row so the staff member does not start from zero. This includes technical failures, where there may be no order id yet. That is why `order_id` is allowed to be empty. If even that write fails, the reply must not claim "forwarded".

## An old file, handled kindly

If an old database file with the first schema exists, `_connect` renames its table to `service_requests_legacy_v1` instead of deleting it. We never destroy data to make our own life easier.

> [!honest] Found while writing this guide, and fixed: a concurrency test failed about half the time with "database is locked". The cause was a real race. The very first connections to a fresh file all tried to switch it into WAL mode at once, and that switch needs an exclusive lock that does not wait on the busy timeout. The fix: check whether the file is already in WAL mode, and retry the switch briefly if it is locked. WAL is stored in the file, so only the first connections ever need it. Twelve runs in a row passed afterwards.

## Check yourself

```quiz
Q: Why can two simultaneous writers never get the same SR id now?
- Python locks the file
* SQLite generates the number inside the insert itself
- We sleep a random time
- The model picks it
? AUTOINCREMENT is assigned by the database during the write, so there is no gap to race in.

Q: A customer asks to cancel the same order twice. What do they get the second time?
- An error
- A second request
* The same request id as the first time
- Nothing
? The partial unique index on open requests makes the second insert a no-op, and we return the existing id.
```
