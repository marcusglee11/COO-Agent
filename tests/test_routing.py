import pytest
import sqlite3
from datetime import datetime
from project_builder.database.migrations import apply_schema
from project_builder.orchestrator.routing import validate_and_log_route

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("m1", "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    conn.commit()
    yield conn
    conn.close()

def test_allowed_routes(db_conn):
    assert validate_and_log_route(db_conn, "m1", "COO", "Engineer")
    assert validate_and_log_route(db_conn, "m1", "Engineer", "COO")
    assert validate_and_log_route(db_conn, "m1", "COO", "QA")
    assert validate_and_log_route(db_conn, "m1", "QA", "COO")
    assert validate_and_log_route(db_conn, "m1", "COO", "Planner")
    assert validate_and_log_route(db_conn, "m1", "Planner", "COO")
    assert validate_and_log_route(db_conn, "m1", "COO", "CEO")
    assert validate_and_log_route(db_conn, "m1", "CEO", "COO")
    
    # No event logged
    cur = db_conn.execute("SELECT COUNT(*) FROM timeline_events")
    assert cur.fetchone()[0] == 0

def test_illegal_routes(db_conn):
    assert not validate_and_log_route(db_conn, "m1", "Planner", "Engineer")
    assert not validate_and_log_route(db_conn, "m1", "Engineer", "QA")
    assert not validate_and_log_route(db_conn, "m1", "QA", "Engineer")
    assert not validate_and_log_route(db_conn, "m1", "Engineer", "Planner")
    
    # Events logged
    cur = db_conn.execute("SELECT COUNT(*) FROM timeline_events WHERE event_type='illegal_message_route'")
    assert cur.fetchone()[0] == 4
