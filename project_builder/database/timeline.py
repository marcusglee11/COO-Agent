import uuid
import json
import sqlite3
from datetime import datetime

# Fixed namespace from Packet §4.3
TIMELINE_NAMESPACE = uuid.UUID('00000000-0000-0000-0000-000000000001')

# Per-task monotonic counter maintained in memory
# Note: In a real distributed system this might need to be more robust,
# but for this single-process agent, a global dict is a reasonable start,
# or we rely on the caller to provide the counter.
# The packet says "maintained in memory".
_task_counters: dict[str, int] = {}

def _get_next_counter(task_id: str) -> int:
    count = _task_counters.get(task_id, 0)
    _task_counters[task_id] = count + 1
    return count

def reset_counters_for_testing() -> None:
    """
    Resets the task counters. ONLY for use in tests.
    """
    global _task_counters
    _task_counters = {}

def generate_timeline_event_id(mission_id: str, task_id: str, event_type: str, created_at: datetime) -> str:
    """
    Generates a deterministic UUIDv5 for a timeline event.
    """
    # Truncate created_at to milliseconds
    # ISO format with milliseconds: YYYY-MM-DDTHH:MM:SS.mmm
    created_at_str = created_at.isoformat(timespec='milliseconds')
    
    counter = _get_next_counter(task_id)
    
    name = f"{mission_id}:{task_id}:{event_type}:{created_at_str}:{counter}"
    return str(uuid.uuid5(TIMELINE_NAMESPACE, name))

def log_event(conn: sqlite3.Connection, mission_id: str, task_id: str, event_type: str, metadata: dict, created_at: datetime) -> None:
    """
    Logs a timeline event to the database.
    """
    event_id = generate_timeline_event_id(mission_id, task_id, event_type, created_at)
    event_json = json.dumps(metadata)
    
    conn.execute("""
        INSERT INTO timeline_events (id, mission_id, task_id, event_type, event_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (event_id, mission_id, task_id, event_type, event_json, created_at))

def log_task_repair_requested(conn: sqlite3.Connection, mission_id: str, task_id: str, reason: str, created_at: datetime) -> None:
    log_event(conn, mission_id, task_id, 'task_repair_requested', {'reason': reason}, created_at)

def log_repair_context_truncated(conn: sqlite3.Connection, mission_id: str, task_id: str, original_length: int, created_at: datetime) -> None:
    log_event(conn, mission_id, task_id, 'repair_context_truncated', {'original_length': original_length, 'truncated_length': 2000}, created_at)

def log_required_artifact_ids_limit_exceeded(conn: sqlite3.Connection, mission_id: str, task_id: str, count: int, created_at: datetime) -> None:
    log_event(conn, mission_id, task_id, 'required_artifact_ids_limit_exceeded', {'count': count, 'limit': 3}, created_at)

def log_task_reclaim_skipped_alive_or_unknown(conn: sqlite3.Connection, mission_id: str, task_id: str, locked_by: str, created_at: datetime) -> None:
    log_event(conn, mission_id, task_id, 'task_reclaim_skipped_alive_or_unknown', {'locked_by': locked_by}, created_at)
