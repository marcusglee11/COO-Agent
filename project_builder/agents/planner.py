import json

def validate_required_artifact_ids(required_artifact_ids: list[str] | None) -> None:
    """
    Validates the required_artifact_ids list per Packet §4.1.
    Must be a list of strings with max 3 items.
    """
    if required_artifact_ids is None:
        return

    if not isinstance(required_artifact_ids, list):
        raise ValueError("required_artifact_ids must be a list")

    if len(required_artifact_ids) > 3:
        raise ValueError("required_artifact_ids_limit_exceeded")

    for item in required_artifact_ids:
        if not isinstance(item, str):
            raise ValueError("required_artifact_ids items must be strings")

def validate_plan_budget(total_task_budget: float, mission_max_budget: float) -> None:
    """
    Validates that the sum of all task budgets does not exceed 80% of the Mission Max Budget
    per Packet §5.6.
    """
    limit = mission_max_budget * 0.80
    if total_task_budget > limit:
        raise ValueError(f"Plan budget {total_task_budget} exceeds 80% of mission max {mission_max_budget} (Limit: {limit})")
