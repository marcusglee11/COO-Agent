import pytest
import sqlite3
from project_builder.database import verify_json1
from project_builder.database.migrations import apply_schema

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    yield conn
    conn.close()

def test_json1_available(db_conn):
    """Verify JSON1 extension is available."""
    verify_json1(db_conn)
    # Also verify directly
    cur = db_conn.execute("SELECT json_valid('[1]')")
    assert cur.fetchone()[0] == 1

def test_tables_exist(db_conn):
    """Verify all required tables exist."""
    cur = db_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    expected = {'missions', 'mission_tasks', 'artifacts', 'timeline_events'}
    assert expected.issubset(tables)

def test_columns_exist(db_conn):
    """Verify critical columns exist."""
    # Helper to get columns
    def get_columns(table):
        cur = db_conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}

    missions_cols = get_columns('missions')
    assert 'repair_budget_usd' in missions_cols
    assert 'plan_revision_count' in missions_cols

    tasks_cols = get_columns('mission_tasks')
    assert 'required_artifact_ids' in tasks_cols
    assert 'tokenizer_model' in tasks_cols
    assert 'repair_budget_spent_usd' in tasks_cols

    artifacts_cols = get_columns('artifacts')
    assert 'file_path' in artifacts_cols
    assert 'version_number' in artifacts_cols
    assert 'is_deleted' in artifacts_cols

def test_indexes_exist(db_conn):
    """Verify required indexes exist."""
    cur = db_conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in cur.fetchall()}
    
    expected = {
        'idx_artifacts_snapshot',
        'idx_artifacts_required',
        'idx_timeline_task',
        'idx_artifacts_project_state',
        'idx_artifacts_mission_created',
        'idx_timeline_mission'
    }
    assert expected.issubset(indexes)
