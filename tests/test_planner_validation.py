import pytest
import sqlite3
from project_builder.agents.planner import validate_required_artifact_ids, validate_plan_budget
from project_builder.database.migrations import apply_schema
from project_builder.config.settings import PLANNER_BUDGET_FRACTION

@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    apply_schema(conn)
    conn.execute("INSERT INTO missions (id, status, description, max_cost_usd, max_loops, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 ("m1", "executing", "desc", 100.0, 5, "now", "now"))
    conn.commit()
    yield conn
    conn.close()

def test_validate_required_artifact_ids_valid():
    """Test valid inputs for required_artifact_ids."""
    validate_required_artifact_ids(None)
    validate_required_artifact_ids([])
    validate_required_artifact_ids(["a1"])
    validate_required_artifact_ids(["a1", "a2", "a3"])

def test_validate_required_artifact_ids_invalid_type():
    """Test invalid types."""
    with pytest.raises(ValueError, match="must be a list"):
        validate_required_artifact_ids("not a list") # type: ignore
    
    with pytest.raises(ValueError, match="must be strings"):
        validate_required_artifact_ids([1, 2]) # type: ignore

def test_validate_required_artifact_ids_limit_exceeded():
    """Test limit exceeded."""
    with pytest.raises(ValueError, match="required_artifact_ids_limit_exceeded"):
        validate_required_artifact_ids(["a1", "a2", "a3", "a4"])

def test_validate_plan_budget_valid(db_conn):
    """Test valid budget."""
    # Limit is 80.0
    validate_plan_budget(db_conn, "m1", 80.0)
    validate_plan_budget(db_conn, "m1", 50.0)

def test_validate_plan_budget_exceeded(db_conn):
    """Test budget exceeded."""
    # Limit is 80.0
    with pytest.raises(ValueError, match="exceeds 80.0%"):
        validate_plan_budget(db_conn, "m1", 80.1)
