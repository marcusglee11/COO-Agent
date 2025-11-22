import pytest
import sqlite3
import threading
import os
from project_builder.database.migrations import apply_schema
from project_builder.orchestrator.budget_txn import try_charge_budget

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    apply_schema(conn)
    # Insert mission
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, repair_budget_usd, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                 ("m1", "executing", "desc", 10.0, 5, 2.0))
    conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status) VALUES (?, ?, ?, ?, ?)",
                 ("t1", "m1", 1, "task1", "executing"))
    conn.commit()
    yield conn
    conn.close()

def test_budget_charge_success(db_conn):
    assert try_charge_budget(db_conn, "m1", "t1", 1.0, False)
    cur = db_conn.execute("SELECT spent_cost_usd FROM missions WHERE id='m1'")
    assert cur.fetchone()[0] == 1.0

def test_budget_charge_fail_mission_limit(db_conn):
    assert not try_charge_budget(db_conn, "m1", "t1", 11.0, False)
    cur = db_conn.execute("SELECT spent_cost_usd FROM missions WHERE id='m1'")
    assert cur.fetchone()[0] == 0.0

def test_budget_charge_repair_success(db_conn):
    assert try_charge_budget(db_conn, "m1", "t1", 1.0, True)
    cur = db_conn.execute("SELECT spent_cost_usd FROM missions WHERE id='m1'")
    assert cur.fetchone()[0] == 1.0
    cur = db_conn.execute("SELECT repair_budget_spent_usd FROM mission_tasks WHERE id='t1'")
    assert cur.fetchone()[0] == 1.0

def test_budget_charge_repair_fail_limit(db_conn):
    # Mission limit 10, Repair limit 2
    # Charge 3 (fails repair limit)
    assert not try_charge_budget(db_conn, "m1", "t1", 3.0, True)
    cur = db_conn.execute("SELECT spent_cost_usd FROM missions WHERE id='m1'")
    assert cur.fetchone()[0] == 0.0 # Rolled back
    cur = db_conn.execute("SELECT repair_budget_spent_usd FROM mission_tasks WHERE id='t1'")
    assert cur.fetchone()[0] == 0.0

def test_budget_concurrent_access():
    # Use a file DB for concurrency test
    db_path = "test_budget_concurrency.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
        
    conn = sqlite3.connect(db_path, check_same_thread=False)
    apply_schema(conn)
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, repair_budget_usd, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                 ("m1", "executing", "desc", 10.0, 5, 5.0))
    conn.commit()
    conn.close()
    
    def charge_worker(cost):
        try:
            with sqlite3.connect(db_path, timeout=10.0) as c:
                c.execute("PRAGMA busy_timeout = 10000")
                try_charge_budget(c, "m1", None, cost, False)
        except sqlite3.OperationalError:
            pass
        except Exception:
            pass
        
    threads = []
    for _ in range(10):
        t = threading.Thread(target=charge_worker, args=(1.0,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT spent_cost_usd FROM missions WHERE id='m1'")
    spent = cur.fetchone()[0]
    conn.close()
    
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
    
    assert spent > 0
    assert spent <= 10.0
    assert spent % 1.0 == 0
