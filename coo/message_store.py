import structlog
log = structlog.get_logger()
import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta

class MessageStore:
    HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes
    
    def __init__(self, db_path: Path, worker_id: str = None):
        self.db_path = db_path
        self.worker_id = worker_id or f"{Path.home().name}_{id(self)}"
    
    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA synchronous = NORMAL")
            await db.execute("PRAGMA busy_timeout = 5000")

            # === missions ===
            await db.execute("""
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
            """)

            # === messages ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    body_json TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 5,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    timeout_at DATETIME,
                    locked_at DATETIME,
                    locked_by TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # === artifacts ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    type TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    storage_type TEXT NOT NULL DEFAULT 'inline',
                    path TEXT,
                    checksum TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    created_by TEXT NOT NULL
                )
            """)

            # === agents ===
            await db.execute("""
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
            """)

            # === dead_letters ===
            await db.execute("""
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
            """)

            # === timeline_events ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS timeline_events (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    event_type TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at DATETIME NOT NULL
                )
            """)

            # === budgets_global ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS budgets_global (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    daily_budget_usd REAL NOT NULL,
                    daily_spent_usd REAL NOT NULL DEFAULT 0,
                    monthly_budget_usd REAL NOT NULL,
                    monthly_spent_usd REAL NOT NULL DEFAULT 0,
                    updated_at DATETIME NOT NULL
                )
            """)

            # === sandbox_runs ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sandbox_runs (
                    dedupe_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL REFERENCES missions(id),
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    status TEXT NOT NULL,
                    result_artifact_id TEXT,
                    exit_code INTEGER,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME
                )
            """)

            await db.commit()
    
    async def claim_pending_messages(self, to_agent: str,
                                     mission_id: str, limit: int = 1) -> list[dict]:
        """Atomically claim pending messages for an agent"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE messages
                SET status = 'processing',
                    locked_at = CURRENT_TIMESTAMP,
                    locked_by = ?
                WHERE id IN (
                    SELECT id FROM messages
                    WHERE to_agent = ?
                      AND mission_id = ?
                      AND status = 'pending'
                      AND (timeout_at IS NULL OR timeout_at > CURRENT_TIMESTAMP)
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                )
                RETURNING *
            """, (self.worker_id, to_agent, mission_id, limit))

            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            await db.commit()
            return [{columns[i]: row[i] for i in range(len(columns))} for row in rows]
    
    async def deliver_message(self, msg: dict):
        """Insert a new message"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO messages 
                (id, mission_id, from_agent, to_agent, kind, status, body_json,
                 priority, max_retries, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                msg["id"], msg["mission_id"], msg["from_agent"], 
                msg["to_agent"], msg["kind"], msg["body_json"],
                msg.get("priority", 5), msg.get("max_retries", 3)
            ))
            await db.commit()
    
    async def reclaim_stale_messages(self) -> int:
        """Reclaim messages locked by dead workers"""
        stale_cutoff = datetime.utcnow() - timedelta(seconds=self.HEARTBEAT_TIMEOUT_SECONDS)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                UPDATE messages
                SET status = 'pending', 
                    locked_at = NULL, 
                    locked_by = NULL,
                    retry_count = retry_count + 1
                WHERE status = 'processing'
                  AND locked_at < ?
                  AND retry_count < max_retries
                RETURNING id, mission_id, to_agent
            """, (stale_cutoff,))
            
            reclaimed = await cursor.fetchall()
            await db.commit()
            
            for msg in reclaimed:
                log.warning("message_reclaimed", 
                           message_id=msg["id"], 
                           mission_id=msg["mission_id"],
                           to_agent=msg["to_agent"])
            
            return len(reclaimed)
