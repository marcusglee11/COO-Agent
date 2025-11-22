import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from project_builder.database.migrations import apply_schema
from project_builder.database.snapshot import snapshot_query

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    yield conn
    conn.close()

def test_snapshot_basic(db_conn):
    """Test basic snapshot retrieval."""
    mid = "m1"
    tid = "t1"
    
    # Setup mission and task
    db_conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (mid, "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    
    started_at = datetime.utcnow()
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, started_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (tid, mid, 1, "task1", "executing", started_at, datetime.utcnow()))
    
    # Insert artifact
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a1", mid, "file1.txt", 1, "file", started_at - timedelta(seconds=10), b"content1"))
    
    results = snapshot_query(db_conn, mid, tid)
    assert len(results) == 1
    assert results[0][0] == "file1.txt"
    assert results[0][1] == b"content1"

def test_snapshot_versioning(db_conn):
    """Test that latest version is picked."""
    mid = "m1"
    tid = "t1"
    
    started_at = datetime.utcnow()
    
    # Setup mission and task
    db_conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (mid, "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, started_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (tid, mid, 1, "task1", "executing", started_at, datetime.utcnow()))
    
    # v1
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a1", mid, "file1.txt", 1, "file", started_at - timedelta(seconds=20), b"v1"))
    
    # v2 (should be picked)
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a2", mid, "file1.txt", 2, "file", started_at - timedelta(seconds=10), b"v2"))
    
    results = snapshot_query(db_conn, mid, tid)
    assert len(results) == 1
    assert results[0][0] == "file1.txt"
    assert results[0][1] == b"v2"

def test_snapshot_tombstone(db_conn):
    """Test that deleted files are excluded."""
    mid = "m1"
    tid = "t1"
    
    started_at = datetime.utcnow()
    
    # Setup mission and task
    db_conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (mid, "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, started_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (tid, mid, 1, "task1", "executing", started_at, datetime.utcnow()))
    
    # v1
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a1", mid, "file1.txt", 1, "file", started_at - timedelta(seconds=20), b"v1"))
    
    # v2 (deleted)
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a2", mid, "file1.txt", 2, "file", started_at - timedelta(seconds=10), 1))
    
    results = snapshot_query(db_conn, mid, tid)
    assert len(results) == 0

def test_snapshot_required_artifact_override(db_conn):
    """Test that required_artifact_ids overrides versioning and deletion."""
    mid = "m1"
    tid = "t1"
    
    started_at = datetime.utcnow()
    
    # Setup mission and task with required_artifact_ids pointing to v1
    db_conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (mid, "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, started_at, created_at, required_artifact_ids) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (tid, mid, 1, "task1", "executing", started_at, datetime.utcnow(), json.dumps(["a1"])))
    
    # v1 (required)
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a1", mid, "file1.txt", 1, "file", started_at - timedelta(seconds=20), b"v1"))
    
    # v2 (deleted, would normally hide v1)
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, is_deleted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a2", mid, "file1.txt", 2, "file", started_at - timedelta(seconds=10), 1))
    
    results = snapshot_query(db_conn, mid, tid)
    assert len(results) == 1
    assert results[0][0] == "file1.txt"
    assert results[0][1] == b"v1"

def test_snapshot_ordering(db_conn):
    """
    Test that snapshot returns files sorted alphabetically by file_path,
    regardless of insertion order.
    """
    mid = "m1"
    tid = "t1"
    
    started_at = datetime.utcnow()
    
    # Setup mission and task
    db_conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (mid, "executing", "desc", 10.0, 5, datetime.utcnow(), datetime.utcnow()))
    db_conn.execute("INSERT INTO mission_tasks (id, mission_id, task_order, description, status, started_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (tid, mid, 1, "task1", "executing", started_at, datetime.utcnow()))
    
    # Insert z.txt first
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a1", mid, "z.txt", 1, "file", started_at - timedelta(seconds=20), b"content_z"))
    
    # Insert a.txt second
    db_conn.execute("""
        INSERT INTO artifacts (id, mission_id, file_path, version_number, kind, created_at, content)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("a2", mid, "a.txt", 1, "file", started_at - timedelta(seconds=10), b"content_a"))
    
    results = snapshot_query(db_conn, mid, tid)
    assert len(results) == 2
    assert results[0][0] == "a.txt"
    assert results[0][1] == b"content_a"
    assert results[1][0] == "z.txt"
    assert results[1][1] == b"content_z"
