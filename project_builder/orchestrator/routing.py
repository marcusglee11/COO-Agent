import sqlite3
from datetime import datetime
from project_builder.database.timeline import log_event

ALLOWED_ROUTES = {
    ("COO", "Engineer"),
    ("Engineer", "COO"),
    ("COO", "QA"),
    ("QA", "COO"),
    ("COO", "Planner"),
    ("Planner", "COO"),
    ("COO", "CEO"),
    ("CEO", "COO"),
    ("User", "COO"),
    ("COO", "User"),
}

def is_route_allowed(from_agent: str, to_agent: str) -> bool:
    return (from_agent, to_agent) in ALLOWED_ROUTES

def validate_and_log_route(conn: sqlite3.Connection, mission_id: str, from_agent: str, to_agent: str) -> bool:
    """
    Checks if route is allowed. If not, logs a timeline event.
    Returns True if allowed, False otherwise.
    """
    if is_route_allowed(from_agent, to_agent):
        return True
        
    log_event(conn, mission_id, None, 'illegal_message_route', 
              {'from': from_agent, 'to': to_agent}, datetime.utcnow())
    return False
