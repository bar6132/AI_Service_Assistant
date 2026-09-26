"""Service-request store, SQLite. Source: design doc lines 130, 265, 357."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "service_requests.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS service_requests (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    summary TEXT NOT NULL,
    source_ids TEXT NOT NULL,
    run_id TEXT NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def _next_id(conn: sqlite3.Connection) -> str:
    count = conn.execute("SELECT COUNT(*) FROM service_requests").fetchone()[0]
    return f"SR-{count + 1:06d}"


def create_request(
    customer_id: str,
    order_id: str,
    type_: str,
    source_ids: list[str],
    summary: str,
    run_id: str,
) -> str:
    """Creates a record, or returns the id of an existing open request of the
    same type for the same order (idempotent — design line 265: "אם כבר קיימת
    בקשה פתוחה מאותו סוג לאותה הזמנה, מוחזר המזהה הקיים"). Only real action
    performed is this DB write — no actual cancellation/refund (test line 85).
    """
    conn = _connect()
    try:
        existing = conn.execute(
            "SELECT id FROM service_requests WHERE order_id = ? AND type = ? AND status = 'open'",
            (order_id, type_),
        ).fetchone()
        if existing:
            return existing[0]

        new_id = _next_id(conn)
        conn.execute(
            "INSERT INTO service_requests "
            "(id, created_at, customer_id, order_id, type, status, summary, source_ids, run_id) "
            "VALUES (?, datetime('now'), ?, ?, ?, 'open', ?, ?, ?)",
            (new_id, customer_id, order_id, type_, summary, ",".join(source_ids), run_id),
        )
        conn.commit()
        return new_id
    finally:
        conn.close()
