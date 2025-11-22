import json
import sqlite3
from project_builder.config.settings import PLANNER_BUDGET_FRACTION

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

def validate_plan_budget(conn: sqlite3.Connection, mission_id: str, estimated_cost_usd: float) -> None:
    """
    Validates that the sum of all task budgets does not exceed 80% of the Mission Max Budget
    per Packet §5.6.
    """
    cur = conn.execute("SELECT max_cost_usd FROM missions WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("mission_not_found")
        
    max_cost_usd = row[0]
    limit = max_cost_usd * PLANNER_BUDGET_FRACTION
    
    if estimated_cost_usd > limit:
        raise ValueError(f"Plan budget {estimated_cost_usd} exceeds {PLANNER_BUDGET_FRACTION*100}% of mission max {max_cost_usd} (Limit: {limit})")
