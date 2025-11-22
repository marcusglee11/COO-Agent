import pytest
import sqlite3
from project_builder.database.migrations import apply_schema
from project_builder.orchestrator.missions import check_and_apply_backpressure, compute_backpressure_thresholds
from project_builder.config.settings import BASE_PENDING_LIMIT

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    # Create messages table manually since it's not in schema.sql (it's in coo_core)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at DATETIME NOT NULL
        )
    """)
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("m1", "executing", "desc", 10.0, 5, "now", "now"))
    conn.commit()
    yield conn
    conn.close()

def test_compute_thresholds():
    # Base case
    max_p, resume = compute_backpressure_thresholds(1)
    assert max_p == BASE_PENDING_LIMIT # 50
    assert resume == 30 # 60% of 50
    
    # Scaling case
    # 10 tasks * 10 = 100
    max_p, resume = compute_backpressure_thresholds(10)
    assert max_p == 100
    assert resume == 60

def test_backpressure_pause(db_conn):
    # 1 task, limit 50
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status) VALUES (?, ?, ?, ?, ?)",
                    ("t1", "m1", 1, "desc", "executing"))
    
    # Insert 51 pending messages
    for i in range(51):
        db_conn.execute("INSERT INTO messages (id, mission_id, status, created_at) VALUES (?, ?, ?, ?)",
                        (f"msg{i}", "m1", "pending", "now"))
    db_conn.commit()
    
    check_and_apply_backpressure(db_conn, "m1")
    
    cur = db_conn.execute("SELECT status, previous_status, failure_reason FROM missions WHERE id='m1'")
    row = cur.fetchone()
    assert row[0] == "paused_error"
    assert row[1] == "executing"
    assert row[2] == "task_backpressure"
    
    # Verify event
    cur = db_conn.execute("SELECT event_type FROM timeline_events WHERE mission_id='m1'")
    assert cur.fetchone()[0] == "mission_paused_backpressure"

def test_backpressure_resume(db_conn):
    # Setup paused state
    db_conn.execute("UPDATE missions SET status='paused_error', previous_status='executing' WHERE id='m1'")
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status) VALUES (?, ?, ?, ?, ?)",
                    ("t1", "m1", 1, "desc", "executing"))
    
    # 1 task, limit 50, resume 30
    # Insert 29 pending messages (below resume)
    for i in range(29):
        db_conn.execute("INSERT INTO messages (id, mission_id, status, created_at) VALUES (?, ?, ?, ?)",
                        (f"msg{i}", "m1", "pending", "now"))
    db_conn.commit()
    
    check_and_apply_backpressure(db_conn, "m1")
    
    cur = db_conn.execute("SELECT status, previous_status FROM missions WHERE id='m1'")
    row = cur.fetchone()
    assert row[0] == "executing"
    assert row[1] is None
    
    # Verify event
    cur = db_conn.execute("SELECT event_type FROM timeline_events WHERE mission_id='m1' AND event_type='mission_resumed_backpressure'")
    assert cur.fetchone()
