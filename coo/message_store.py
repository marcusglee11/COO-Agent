import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
import structlog

log = structlog.get_logger()


class MessageStore:
    HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes

    def __init__(self, db_path: Path, worker_id: str = None):
        self.db_path = db_path
        # Simple worker ID generation if not provided
        self.worker_id = worker_id or f"worker_{id(self)}"

    async def initialize(self):
        """Create tables if they don't exist"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA synchronous = NORMAL")
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA busy_timeout = 5000")

            # Missions table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    previous_status TEXT,
                    description TEXT NOT NULL,
                    max_cost_usd REAL NOT NULL,
                    max_loops INTEGER NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 5,
                    budget_increase_requests INTEGER NOT NULL DEFAULT 0,
                    config_json TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    failed_at DATETIME,
                    failure_reason TEXT,
                    spent_cost_usd REAL NOT NULL DEFAULT 0,
                    loop_count INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0
                )
            """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status)"
            )

            # Messages table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    schema_version INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 5,
                    correlation_id TEXT,
                    conversation_id TEXT,
                    in_reply_to TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    timeout_at DATETIME,
                    locked_at DATETIME,
                    locked_by TEXT,
                    error_type TEXT,
                    error_detail TEXT,
                    created_at DATETIME NOT NULL,
                    processed_at DATETIME
                )
            """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_pending ON messages(to_agent, status, mission_id) WHERE status = 'pending'"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_mission ON messages(mission_id, created_at)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_stale ON messages(locked_at, status) WHERE status = 'processing' AND locked_at IS NOT NULL"
            )

            # Artifacts table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    filename TEXT,
                    mime_type TEXT,
                    content_b64 TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    created_by TEXT NOT NULL
                )
            """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_mission ON artifacts(mission_id, created_at)"
            )

            # Agents registry
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    name TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_active DATETIME,
                    error_streak INTEGER NOT NULL DEFAULT 0,
                    total_invocations INTEGER NOT NULL DEFAULT 0,
                    total_cost_usd REAL NOT NULL DEFAULT 0,
                    avg_duration_ms REAL,
                    success_rate REAL,
                    capabilities_json TEXT,
                    config_json TEXT
                )
            """
            )

            # Dead-letter queue
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS dead_letters (
                    id TEXT PRIMARY KEY,
                    original_message_id TEXT NOT NULL REFERENCES messages(id),
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    failed_at DATETIME NOT NULL,
                    error_type TEXT NOT NULL,
                    error_detail TEXT,
                    retry_count INTEGER NOT NULL,
                    payload_snapshot TEXT NOT NULL
                )
            """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_dead_letters_mission ON dead_letters(mission_id, failed_at)"
            )

            # Timeline events
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS timeline_events (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                )
            """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_timeline_mission ON timeline_events(mission_id, created_at)"
            )

            # Budget tracking (global)
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS budgets_global (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    daily_budget_usd REAL NOT NULL,
                    daily_spent_usd REAL NOT NULL DEFAULT 0,
                    monthly_budget_usd REAL NOT NULL,
                    monthly_spent_usd REAL NOT NULL DEFAULT 0,
                    updated_at DATETIME NOT NULL
                )
            """
            )

            # Sandbox runs
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sandbox_runs (
                    dedupe_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    status TEXT NOT NULL,
                    result_artifact_id TEXT,
                    exit_code INTEGER,
                    stdout TEXT,
                    stderr TEXT,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME
                )
            """
            )
            await db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_sandbox_dedupe ON sandbox_runs(dedupe_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sandbox_runs_mission ON sandbox_runs(mission_id, started_at)"
            )

            await db.commit()

    async def claim_pending_messages(
        self, to_agent: str, mission_id: str = None, limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Atomically claim pending messages for an agent"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Build query dynamically based on mission_id presence
            mission_clause = "AND mission_id = ?" if mission_id else ""
            params = [self.worker_id, to_agent]
            if mission_id:
                params.append(mission_id)
            params.append(limit)
            
            cursor = await db.execute(
                f"""
                UPDATE messages
                SET status = 'processing', 
                    locked_at = CURRENT_TIMESTAMP,
                    locked_by = ?
                WHERE id IN (
                    SELECT id FROM messages
                    WHERE to_agent = ? 
                      {mission_clause}
                      AND status = 'pending'
                      AND (timeout_at IS NULL OR timeout_at > CURRENT_TIMESTAMP)
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                )
                RETURNING *
            """,
                tuple(params),
            )

            rows = await cursor.fetchall()
            await db.commit()

            results = []
            for row in rows:
                d = dict(row)
                if isinstance(d.get("body_json"), str):
                    try:
                        d["body_json"] = json.loads(d["body_json"])
                    except json.JSONDecodeError:
                        pass
                results.append(d)
            return results

    async def deliver_message(self, msg: Dict[str, Any]):
        """Insert a new message"""
        body_json = msg["body_json"]
        if isinstance(body_json, dict):
            body_json = json.dumps(body_json)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages 
                (id, mission_id, from_agent, to_agent, kind, status, body_json,
                 priority, max_retries, created_at, correlation_id, conversation_id, in_reply_to)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
                (
                    msg["id"],
                    msg["mission_id"],
                    msg["from_agent"],
                    msg["to_agent"],
                    msg["kind"],
                    body_json,
                    msg.get("priority", 5),
                    msg.get("max_retries", 3),
                    msg.get("correlation_id"),
                    msg.get("conversation_id"),
                    msg.get("in_reply_to"),
                ),
            )
            await db.commit()

    async def reclaim_stale_messages(self) -> int:
        """Reclaim messages locked by dead workers"""
        stale_cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self.HEARTBEAT_TIMEOUT_SECONDS
        )

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                UPDATE messages
                SET status = 'pending', 
                    locked_at = NULL, 
                    locked_by = NULL,
                    retry_count = retry_count + 1
                WHERE status = 'processing'
                  AND locked_at < ?
                  AND retry_count < max_retries
                RETURNING id, mission_id, to_agent
            """,
                (stale_cutoff,),
            )

            reclaimed = await cursor.fetchall()
            await db.commit()

            for row in reclaimed:
                msg = dict(row)
                log.warning(
                    "message_reclaimed",
                    message_id=msg["id"],
                    mission_id=msg["mission_id"],
                    to_agent=msg["to_agent"],
                )

            return len(reclaimed)

    async def create_mission(self, mission_data: Dict[str, Any]):
        """Create a new mission"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO missions
                (id, status, description, max_cost_usd, max_loops, created_at, updated_at, config_json)
                VALUES (?, 'created', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
            """,
                (
                    mission_data["id"],
                    mission_data["description"],
                    mission_data.get("max_cost_usd", 5.0),
                    mission_data.get("max_loops", 20),
                    mission_data.get("config_json", "{}"),
                ),
            )
            await db.commit()

    async def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Get mission by ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM missions WHERE id = ?", (mission_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_mission_history(self, mission_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent message history for a mission, sorted by creation time"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM messages 
                WHERE mission_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
                """, 
                (mission_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                # Return reversed (oldest first) for LLM context
                return [dict(row) for row in reversed(rows)]

    async def count_pending_messages(self, mission_id: str) -> int:
        """Count pending messages for a mission"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM messages WHERE mission_id = ? AND status = 'pending'",
                (mission_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    
    async def update_mission_status(self, mission_id: str, status: str):
        """Update mission status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE missions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, mission_id),
            )
            await db.commit()
