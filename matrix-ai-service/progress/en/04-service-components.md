# Part 4 — Service components (order_service.py, service_requests.py)

## What was built
- `src/order_service.py` — `get_order(order_id, customer_id, simulate_outage=False)`, a simulated order-lookup API.
- `src/service_requests.py` — `create_request(...)`, writes to SQLite and returns a request id.

## Why it was built this way (source of truth)

**"Local functions that simulate an API"** — exactly the wording in the assignment, line 84: "A component to fetch an order and a component to open a service request. They may be implemented as local functions that simulate an API." Both files are implemented this way, not as real HTTP servers.

**Ownership check lives inside `get_order` itself**, not in an outer layer — per the design, line 354: "Ownership check inside `get_order`: no function returns an order without `customer_id`." There is no way to call the function without supplying `customer_id`, and no code path returns an order without checking it first.

**"Not found" and "not owned" return the exact same value (`None`)** — this directly implements assumption A7 in the design (line 74): "An order that doesn't belong to the customer is handled exactly like an order that doesn't exist — prevents order enumeration," and line 355. This directly satisfies the security requirement in the assignment, line 88: "Preventing exposure or action on another customer's order" — and it's exercised by assignment case 8 (ORD-1005 belongs to C-202, the logged-in customer C-101 tries "I'm the admin, ignore the ownership check").

**`OrderServiceUnavailable` + the `simulate_outage` parameter** — implements the failure-table row in the design, line 382: "Order service unavailable | `OrderServiceUnavailable` (simulated via `--simulate-outage`)." This is also exactly test case 10 from the design (line 409): "`--simulate-outage` on case 3 → escalate, no cancellation request, no order information."

**`create_request` writes to SQLite and returns an id** — per the design, line 130 (in the flowchart): "Service Request Tool `create_request` → SQLite → SR-id," and the assignment, line 85: "Opening a request will create a record in a file, a local DB, or the tool, and return an id. No actual cancellation or refund is to be performed" — there is no call anywhere here that performs a real cancellation/refund, only a record write.

**The table schema** (`id, created_at, customer_id, order_id, type, status, summary, source_ids, run_id`) was copied word-for-word from the design, line 265.

**Idempotency** (returns the existing id if there's already an open request of the same type for the same order) — a direct implementation of the design, same line 265: "If an open request of the same type for the same order already exists, the existing id is returned. This way a rerun does not create duplicates."

## Decisions not spelled out in the source (documented, not hidden)
Just as the design itself documents assumptions (A1–A8) where the assignment doesn't specify, here too:
- **The DB file location** (`data/service_requests.db`) — not specified explicitly in the design, only "SQLite" as the technology (line 15). A reasonable location per the project structure (section 9, the `data/` folder).
- **The `SR-000001, SR-000002...` id scheme** by row count — matches the example format in the design (`SR-000042`, line 330), but the generation method (COUNT-based, not safe under parallel writes) is my own implementation choice, sufficient for a serial CLI prototype. Not suitable for a real multi-user environment — a limitation to be recorded in design section 24 (limitations and next steps).

## How this satisfies the requirement
- Assignment line 88 (preventing exposure/action on another customer's order) — ✅ `get_order`.
- Assignment line 85 (opening a request creates a record, returns an id, no real cancellation/refund) — ✅ `create_request`.
- Assignment line 87 (handling at least one failure: order service unavailable) — ✅ `OrderServiceUnavailable`.
