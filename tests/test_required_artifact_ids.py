import pytest
from project_builder.agents.planner import validate_required_artifact_ids

def test_validate_limit_ok():
    validate_required_artifact_ids(["1", "2", "3"])

def test_validate_limit_exceeded():
    with pytest.raises(ValueError, match="required_artifact_ids_limit_exceeded"):
        validate_required_artifact_ids(["1", "2", "3", "4"])

def test_validate_invalid_type():
    with pytest.raises(ValueError, match="must be a list"):
        validate_required_artifact_ids("not a list") # type: ignore

def test_validate_invalid_item_type():
    with pytest.raises(ValueError, match="must be strings"):
        validate_required_artifact_ids([1, 2]) # type: ignore
