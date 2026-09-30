import sqlite3

import pytest

import src.service_requests as service_requests


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Every test that writes service requests gets its own empty database."""
    path = tmp_path / "service_requests.db"
    monkeypatch.setattr(service_requests, "DB_PATH", path)
    return path


def db_rows(path):
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT printf('SR-%06d', seq), customer_id, order_id, type, status "
            "FROM service_requests ORDER BY seq"
        ).fetchall()
    finally:
        conn.close()
