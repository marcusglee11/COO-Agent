import pytest
from project_builder.agents.planner import validate_required_artifact_ids, validate_plan_budget

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

def test_validate_plan_budget_valid():
    """Test valid budget."""
    # 80% of 100 is 80
    validate_plan_budget(80.0, 100.0)
    validate_plan_budget(50.0, 100.0)

def test_validate_plan_budget_exceeded():
    """Test budget exceeded."""
    # 80% of 100 is 80
    with pytest.raises(ValueError, match="exceeds 80%"):
        validate_plan_budget(80.1, 100.0)

