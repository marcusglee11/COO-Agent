import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from project_builder.config.settings import TASK_LOCK_TIMEOUT_SECONDS
from project_builder.database.timeline import log_event, log_task_reclaim_skipped_alive_or_unknown

class WorkerRegistry(ABC):
    @abstractmethod
    def is_alive(self, pid: int) -> bool:
        pass

class PosixWorkerRegistry(WorkerRegistry):
    def is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

class WindowsWorkerRegistry(WorkerRegistry):
    def is_alive(self, pid: int) -> bool:
        # Spec Patch 2: "If liveness cannot be established... reclaim MUST NOT proceed."
        # We return True (Alive) to prevent reclaim on Windows/Unknown platforms
        # as a safety measure until a proper Windows implementation is added.
        return True 

def attempt_reclaim_task(conn: sqlite3.Connection, task_id: str, worker_registry: WorkerRegistry) -> bool:
    """
    Attempts to reclaim a stale-locked task.
    Returns True if reclaim performed, False otherwise.
    """
    cur = conn.cursor()
    cur.execute("SELECT mission_id, locked_by, locked_at FROM mission_tasks WHERE id = ?", (task_id,))
    row = cur.fetchone()
    if not row:
        return False
        
    mission_id, locked_by, locked_at = row
    if not locked_by or not locked_at:
        return False
        
    # Check timeout
    if isinstance(locked_at, str):
        try:
            locked_at_dt = datetime.fromisoformat(locked_at)
        except ValueError:
            # Invalid date format? Treat as stale? Or unsafe?
            # If we can't parse, we can't check timeout.
            # But if it's invalid, maybe we should reclaim?
            # Safer to skip reclaim if data is corrupt.
            return False
    else:
        locked_at_dt = locked_at
        
    if datetime.utcnow() - locked_at_dt < timedelta(seconds=TASK_LOCK_TIMEOUT_SECONDS):
        return False # Not stale
        
    # Check liveness
    try:
        pid = int(locked_by)
        is_alive = worker_registry.is_alive(pid)
    except (ValueError, TypeError):
        # locked_by is not an integer PID -> Unknown/Invalid
        is_alive = True # Treat as alive/unknown
        
    if is_alive:
        log_task_reclaim_skipped_alive_or_unknown(conn, mission_id, task_id, str(locked_by), datetime.utcnow())
        return False
        
    # Reclaim
    try:
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute("""
            UPDATE mission_tasks
            SET status = 'pending',
                locked_at = NULL,
                locked_by = NULL
            WHERE id = :tid
        """, {"tid": task_id})
        
        log_event(conn, mission_id, task_id, 'task_reclaimed', {}, datetime.utcnow())
        conn.commit()
        
        return True
    except Exception:
        conn.rollback()
        return False
