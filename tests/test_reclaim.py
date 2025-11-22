import pytest
import sqlite3
from datetime import datetime, timedelta
from project_builder.database.migrations import apply_schema
from project_builder.orchestrator.reclaim import attempt_reclaim_task, WorkerRegistry
from project_builder.config.settings import TASK_LOCK_TIMEOUT_SECONDS

class MockRegistry(WorkerRegistry):
    def __init__(self, alive_pids):
        self.alive_pids = alive_pids
    def is_alive(self, pid: int) -> bool:
        return pid in self.alive_pids

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("m1", "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    conn.commit()
    yield conn
    conn.close()

def test_reclaim_success(db_conn):
    # Stale task, dead worker
    stale_time = datetime.utcnow() - timedelta(seconds=TASK_LOCK_TIMEOUT_SECONDS + 10)
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, locked_at, locked_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("t1", "m1", 1, "desc", "executing", stale_time, "123"))
    db_conn.commit()
    
    registry = MockRegistry(alive_pids={}) # 123 is dead
    assert attempt_reclaim_task(db_conn, "t1", registry)
    
    cur = db_conn.execute("SELECT status, locked_at, locked_by FROM mission_tasks WHERE id='t1'")
    row = cur.fetchone()
    assert row[0] == "pending"
    assert row[1] is None
    assert row[2] is None
    
    # Verify event
    cur = db_conn.execute("SELECT event_type FROM timeline_events WHERE task_id='t1' AND event_type='task_reclaimed'")
    assert cur.fetchone()

def test_reclaim_skipped_alive(db_conn):
    # Stale task, ALIVE worker
    stale_time = datetime.utcnow() - timedelta(seconds=TASK_LOCK_TIMEOUT_SECONDS + 10)
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, locked_at, locked_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("t1", "m1", 1, "desc", "executing", stale_time, "123"))
    db_conn.commit()
    
    registry = MockRegistry(alive_pids={123}) # 123 is alive
    assert not attempt_reclaim_task(db_conn, "t1", registry)
    
    cur = db_conn.execute("SELECT status FROM mission_tasks WHERE id='t1'")
    assert cur.fetchone()[0] == "executing"
    
    # Verify skipped event
    cur = db_conn.execute("SELECT event_type FROM timeline_events WHERE task_id='t1' AND event_type='task_reclaim_skipped_alive_or_unknown'")
    assert cur.fetchone()

def test_reclaim_not_stale(db_conn):
    # Fresh task
    fresh_time = datetime.utcnow()
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, locked_at, locked_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("t1", "m1", 1, "desc", "executing", fresh_time, "123"))
    db_conn.commit()
    
    registry = MockRegistry(alive_pids={})
    assert not attempt_reclaim_task(db_conn, "t1", registry)
