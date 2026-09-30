import sqlite3
from concurrent.futures import ThreadPoolExecutor

from src.service_requests import create_request
from tests.conftest import db_rows


def _create(order_id, type_="cancellation", customer="C-101"):
    return create_request(customer, order_id, type_, ["POL-04"], "summary", "run-1")


def test_ids_start_at_one_and_increase(temp_db):
    assert _create("ORD-1001") == "SR-000001"
    assert _create("ORD-1002") == "SR-000002"


def test_same_open_request_is_idempotent(temp_db):
    first = _create("ORD-1001")
    assert _create("ORD-1001") == first
    assert len(db_rows(temp_db)) == 1


def test_other_type_on_same_order_is_a_new_request(temp_db):
    assert _create("ORD-1001", "cancellation") != _create("ORD-1001", "agent_handoff")


def test_technical_handoffs_without_order_are_separate_records(temp_db):
    a = create_request("C-101", None, "agent_handoff", ["POL-07"], "outage", "run-1")
    b = create_request("C-101", None, "agent_handoff", ["POL-07"], "outage", "run-2")
    assert a != b
    assert [r[2] for r in db_rows(temp_db)] == [None, None]


def test_concurrent_writers_never_collide(temp_db):
    # Was G-04: COUNT(*)+1 handed two writers the same id -> IntegrityError.
    orders = [f"ORD-{n:04d}" for n in range(200)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(_create, orders))
    assert len(set(ids)) == 200
    assert len(db_rows(temp_db)) == 200


def test_concurrent_same_request_opens_exactly_one(temp_db):
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: _create("ORD-1001"), range(40)))
    assert len(set(ids)) == 1
    assert len(db_rows(temp_db)) == 1


def test_legacy_schema_is_moved_aside(temp_db):
    conn = sqlite3.connect(temp_db)
    conn.execute("CREATE TABLE service_requests (id TEXT PRIMARY KEY, order_id TEXT)")
    conn.execute("INSERT INTO service_requests VALUES ('SR-000001', 'ORD-1001')")
    conn.commit()
    conn.close()

    assert _create("ORD-1002") == "SR-000001"
    conn = sqlite3.connect(temp_db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "service_requests_legacy_v1" in tables
