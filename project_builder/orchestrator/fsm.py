import sqlite3
import json
import re
from datetime import datetime
from project_builder.database.timeline import log_event, log_repair_context_truncated
from project_builder.context.truncation import truncate_repair_context

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")

from project_builder.config.governance import enforce_governance

def validate_id(ident: str, name: str):
    if not ident or not ID_PATTERN.match(ident):
        raise ValueError(f"Invalid {name} format: {ident}")

def check_state(conn: sqlite3.Connection, task_id: str, allowed_states: tuple[str, ...]) -> None:
    cur = conn.execute("SELECT status FROM mission_tasks WHERE id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"Task {task_id} not found")
    if row[0] not in allowed_states:
        raise ValueError(f"Invalid state transition from {row[0]} (allowed: {allowed_states})")

def start_task_execution(conn: sqlite3.Connection, mission_id: str, task_id: str, tokenizer_id: str, now: datetime) -> None:
    """
    Atomically transitions task to 'executing', sets started_at, and records tokenizer.
    """
    validate_id(mission_id, "mission_id")
    validate_id(task_id, "task_id")
    check_state(conn, task_id, ("pending", "repair_retry"))
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
        
        # Enforce Governance (Inside Transaction)
        # CRITICAL: Must be enforced while holding the lock to prevent TOCTOU
        enforce_governance()
        
        # Update status, started_at, and tokenizer_model
        # COALESCE ensures tokenizer is stable if already set
        cur.execute("""
           UPDATE mission_tasks
              SET status = 'executing',
                  started_at = :now,
                  tokenizer_model = COALESCE(tokenizer_model, :tok),
                  updated_at = :now,
                  locked_at = :now,
                  locked_by = 'orchestrator' 
            WHERE id = :tid
        """, {"now": now, "tok": tokenizer_id, "tid": task_id})
        
        if cur.rowcount != 1:
            raise ValueError(f"Task {task_id} update failed")
            
        log_event(conn, mission_id, task_id, 'task_started', {'tokenizer': tokenizer_id}, now)
        
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def transition_to_review(conn: sqlite3.Connection, mission_id: str, task_id: str, result_artifact_ids: list[str], now: datetime) -> None:
    validate_id(mission_id, "mission_id")
    validate_id(task_id, "task_id")
    check_state(conn, task_id, ("executing",))
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
        
        cur.execute("""
            UPDATE mission_tasks
            SET status = 'review',
                result_artifact_ids = :res,
                updated_at = :now,
                locked_at = NULL,
                locked_by = NULL
            WHERE id = :tid
        """, {"res": json.dumps(result_artifact_ids), "now": now, "tid": task_id})
        
        log_event(conn, mission_id, task_id, 'task_review_requested', {}, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def transition_to_approved(conn: sqlite3.Connection, mission_id: str, task_id: str, now: datetime) -> None:
    validate_id(mission_id, "mission_id")
    validate_id(task_id, "task_id")
    check_state(conn, task_id, ("review",))
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
        
        cur.execute("""
            UPDATE mission_tasks
            SET status = 'approved',
                repair_context = NULL,
                updated_at = :now,
                completed_at = :now
            WHERE id = :tid
        """, {"now": now, "tid": task_id})
        
        log_event(conn, mission_id, task_id, 'task_approved', {}, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def transition_to_repair_retry(conn: sqlite3.Connection, mission_id: str, task_id: str, repair_context: str, now: datetime) -> None:
    validate_id(mission_id, "mission_id")
    validate_id(task_id, "task_id")
    check_state(conn, task_id, ("review", "executing")) # Can fail from executing or review
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
        
        # Truncate repair context
        truncated_context = truncate_repair_context(repair_context)
        original_len = len(repair_context)
        truncated_len = len(truncated_context)
        
        cur.execute("""
            UPDATE mission_tasks
            SET status = 'repair_retry',
                repair_attempt = repair_attempt + 1,
                repair_context = :ctx,
                updated_at = :now
            WHERE id = :tid
        """, {"ctx": truncated_context, "now": now, "tid": task_id})
        
        if original_len > truncated_len:
            log_repair_context_truncated(conn, mission_id, task_id, original_len, now)
            
        # Fetch new attempt count for logging
        cur.execute("SELECT repair_attempt FROM mission_tasks WHERE id = :tid", {"tid": task_id})
        new_attempt = cur.fetchone()[0]
        
        log_event(conn, mission_id, task_id, 'task_repair_retry', {'repair_attempt': new_attempt}, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def transition_to_failed_terminal(conn: sqlite3.Connection, mission_id: str, task_id: str, reason: str, now: datetime) -> None:
    validate_id(mission_id, "mission_id")
    validate_id(task_id, "task_id")
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
        
        # Fail the task
        cur.execute("""
            UPDATE mission_tasks
            SET status = 'failed_terminal',
                updated_at = :now,
                repair_context = NULL,
                locked_at = NULL,
                locked_by = NULL
            WHERE id = :tid
        """, {"now": now, "tid": task_id})
        
        # Propagate to mission
        cur.execute("""
            UPDATE missions
            SET status = 'failed',
                failure_reason = :reason,
                failed_at = :now,
                updated_at = :now
            WHERE id = :mid
        """, {"reason": reason, "now": now, "mid": mission_id})
        
        # Skip pending tasks
        cur.execute("""
            UPDATE mission_tasks
            SET status = 'skipped',
                updated_at = :now
            WHERE mission_id = :mid
              AND status IN ('pending', 'repair_retry')
        """, {"now": now, "mid": mission_id})
        
        log_event(conn, mission_id, task_id, 'task_failed_terminal', {'reason': reason}, now)
        log_event(conn, mission_id, None, 'mission_failed', {'reason': reason, 'trigger_task': task_id}, now)
        
        conn.commit()
    except Exception:
        conn.rollback()
        raise
