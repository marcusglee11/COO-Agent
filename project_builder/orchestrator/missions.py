import sqlite3
"""
This module requires the COO core schema (messages table).
Project Builder schema alone is insufficient.
"""
from datetime import datetime
from project_builder.config.settings import BASE_PENDING_LIMIT, MAX_PENDING_PER_TASK
from project_builder.database.timeline import log_event

def compute_backpressure_thresholds(task_count: int) -> tuple[int, int]:
    """Returns (max_pending, resume_threshold) based on Spec §10.5"""
    max_pending = max(BASE_PENDING_LIMIT, task_count * MAX_PENDING_PER_TASK)
    resume_threshold = int(max_pending * 0.6)
    return max_pending, resume_threshold

def check_and_apply_backpressure(conn: sqlite3.Connection, mission_id: str) -> None:
    """
    Checks pending tasks/messages against thresholds and pauses/resumes mission.
    Transitions mission to 'paused_error' if limit exceeded.
    Transitions mission back to 'executing' (or previous) if below resume threshold.
    """
    cur = conn.cursor()
    
    # 1. Get task count
    cur.execute("SELECT COUNT(*) FROM mission_tasks WHERE mission_id = ?", (mission_id,))
    task_count = cur.fetchone()[0]
    
    max_pending, resume_threshold = compute_backpressure_thresholds(task_count)
    
    # 2. Get pending count (tasks + messages)
    # Pending tasks: status IN ('pending', 'repair_retry')
    cur.execute(
        "SELECT COUNT(*) FROM mission_tasks WHERE mission_id = ? AND status IN ('pending', 'repair_retry')",
        (mission_id,)
    )
    pending_tasks = cur.fetchone()[0]
    
    # Pending messages
    cur.execute(
        "SELECT COUNT(*) FROM messages WHERE mission_id = ? AND status = 'pending'",
        (mission_id,)
    )
    pending_messages = cur.fetchone()[0]
    
    total_pending = pending_tasks + pending_messages
    
    # 3. Check Mission Status
    cur.execute("SELECT status, previous_status FROM missions WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    if not row:
        return
    
    current_status, previous_status = row
    
    # 4. Apply Logic
    if current_status not in ('paused_error', 'completed', 'failed'):
        # Check for PAUSE
        if total_pending > max_pending:
            # Transition to paused_error
            cur.execute(
                """
                UPDATE missions 
                SET status = 'paused_error', 
                    previous_status = ?,
                    failure_reason = 'task_backpressure',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (current_status, mission_id)
            )
            
            log_event(conn, mission_id, None, 'mission_paused_backpressure', 
                      {'total_pending': total_pending, 'limit': max_pending}, datetime.utcnow())
            
            conn.commit()
            
    elif current_status == 'paused_error':
        # Check for RESUME
        if total_pending < resume_threshold:
            # Resume to previous status
            resume_status = previous_status or 'executing'
            
            cur.execute(
                """
                UPDATE missions 
                SET status = ?, 
                    previous_status = NULL,
                    failure_reason = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (resume_status, mission_id)
            )
            
            log_event(conn, mission_id, None, 'mission_resumed_backpressure', 
                      {'total_pending': total_pending, 'threshold': resume_threshold}, datetime.utcnow())
            
            conn.commit()
