import pytest
import json
import sqlite3
from datetime import datetime
from project_builder.context.injection import build_context_components
from project_builder.context.truncation import TRUNCATION_MARKER
from project_builder.orchestrator.fsm import start_task_execution
from project_builder.database.migrations import apply_schema

class MockTokenizer:
    def count_tokens(self, text: str) -> int:
        return len(text)
    def truncate(self, text: str, max_tokens: int) -> str:
        return text[:max_tokens]

def test_context_determinism():
    tokenizer = MockTokenizer()
    task = {
        "description": "task1",
        "context_files": json.dumps(["a.txt"])
    }
    snapshot_files = [
        ("a.txt", b"content_a", "2023-01-01T00:00:00"),
        ("b.txt", b"content_b", "2023-01-01T00:00:00")
    ]
    
    # Run 1
    ctx1 = build_context_components(
        "system", "mission", task, snapshot_files, None, None, "tree", tokenizer, 1000
    )
    
    # Run 2
    ctx2 = build_context_components(
        "system", "mission", task, snapshot_files, None, None, "tree", tokenizer, 1000
    )
    
    assert ctx1 == ctx2

def test_context_budget_truncation():
    tokenizer = MockTokenizer()
    task = {
        "description": "task1",
        "context_files": json.dumps(["a.txt"])
    }
    # a.txt is priority (Bucket A)
    # b.txt is Bucket B
    snapshot_files = [
        ("a.txt", b"A" * 100, "2023-01-01T00:00:00"),
        ("b.txt", b"B" * 100, "2023-01-01T00:00:00")
    ]
    
    # Budget large enough for A, small enough to truncate B
    # We calculate exact budget needed for A + overhead
    # Base parts: 
    # system(6) + "Mission: mission"(16) + "Task: task1"(11) + "Project Files:\ntree"(19) = 52
    # File A: "File: a.txt\n```\n{100}\n```" = 12 + 3 + 1 + 100 + 1 + 3 = 120
    # Total used by Base + A = 172
    # Set budget to 250. Remaining = 78.
    # File B overhead: "File: b.txt\n```\n\n```" = 20.
    # Available for B content = 58.
    # So B should be truncated.
    
    ctx = build_context_components(
        "system", "mission", task, snapshot_files, None, None, "tree", tokenizer, 250
    )
    
    # Check A is full
    assert any("A"*100 in c for c in ctx)
    # Check B is truncated
    b_entry = next(c for c in ctx if "b.txt" in c)
    assert TRUNCATION_MARKER in b_entry
    assert "B"*100 not in b_entry

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

def test_tokenizer_persistence_and_replay(db_conn):
    # 1. Start task with tokenizer A
    start_task_execution(db_conn, "m1", "t1", "tokenizer_A", datetime.utcnow())
    
    # 2. Verify DB
    cur = db_conn.execute("SELECT tokenizer_model FROM mission_tasks WHERE id='t1'")
    assert cur.fetchone()[0] == "tokenizer_A"
    
    # 3. Simulate Replay: Reset task to pending and call start_task_execution with tokenizer B
    # The FSM logic uses COALESCE(tokenizer_model, :tok), so if tokenizer_model is already set,
    # it should preserve the original value
    db_conn.execute("UPDATE mission_tasks SET status='pending', started_at=NULL WHERE id='t1'")
    db_conn.commit()
    
    start_task_execution(db_conn, "m1", "t1", "tokenizer_B", datetime.utcnow())
    
    # 4. Verify DB still has A (COALESCE preserved it)
    cur = db_conn.execute("SELECT tokenizer_model FROM mission_tasks WHERE id='t1'")
    assert cur.fetchone()[0] == "tokenizer_A"
