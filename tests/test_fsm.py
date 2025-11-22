import pytest
import sqlite3
from datetime import datetime
from project_builder.database.migrations import apply_schema
from project_builder.orchestrator.fsm import start_task_execution, transition_to_review, transition_to_repair_retry, transition_to_failed_terminal

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("m1", "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status) VALUES (?, ?, ?, ?, ?)",
                 ("t1", "m1", 1, "task1", "pending"))
    conn.commit()
    yield conn
    conn.close()

def test_start_task_execution(db_conn):
    now = datetime.utcnow()
    start_task_execution(db_conn, "m1", "t1", "test_tokenizer", now)
    
    now = datetime.utcnow()
    long_context = "a" * 3000
    transition_to_repair_retry(db_conn, "m1", "t1", long_context, now)
    
    cur = db_conn.execute("SELECT status, repair_attempt, repair_context FROM mission_tasks WHERE id='t1'")
    row = cur.fetchone()
    assert row[0] == "repair_retry"
    assert row[1] == 1
    assert len(row[2]) == 2000 # Truncated
    
    # Verify truncation event
    cur = db_conn.execute("SELECT event_type FROM timeline_events WHERE task_id='t1' AND event_type='repair_context_truncated'")
    assert cur.fetchone()

def test_transition_to_failed_terminal(db_conn):
    now = datetime.utcnow()
    transition_to_failed_terminal(db_conn, "m1", "t1", "error", now)
    
    cur = db_conn.execute("SELECT status FROM mission_tasks WHERE id='t1'")
    assert cur.fetchone()[0] == "failed_terminal"
    
    cur = db_conn.execute("SELECT status, failure_reason FROM missions WHERE id='m1'")
    row = cur.fetchone()
    assert row[0] == "failed"
    assert row[1] == "error"
