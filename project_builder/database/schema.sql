-- GPTCOO v1.1 Project Builder Schema
-- Based on Spec v0.9

-- Table: missions
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,               -- created, planning, executing, reviewing, paused_*, completed, failed
    previous_status TEXT,               -- for resuming from paused_*
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

    failure_reason TEXT,                -- canonical failure reason enum/string
    spent_cost_usd REAL NOT NULL DEFAULT 0,
    loop_count INTEGER NOT NULL DEFAULT 0,
    loop_count_limit INTEGER,           -- from v1.0, not used by Project Builder

    message_count INTEGER NOT NULL DEFAULT 0,

    -- v1.1 additions
    repair_budget_usd REAL NOT NULL DEFAULT 0.0,   -- CAP for repair spend
    plan_revision_count INTEGER NOT NULL DEFAULT 0 -- CEO/Planner revision attempts
);

CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);

-- Table: mission_tasks
CREATE TABLE IF NOT EXISTS mission_tasks (
    id TEXT PRIMARY KEY,                  -- "t1", "t2", ...
    mission_id TEXT NOT NULL REFERENCES missions(id),

    task_order INTEGER NOT NULL,          -- 1..N, contiguous per mission

    description TEXT NOT NULL,            -- human-readable task description

    context_files TEXT,                   -- JSON array of file_paths (Planner suggestions)
    required_artifact_ids TEXT,           -- JSON array of artifact IDs that must be present in snapshot
    repair_context TEXT,                  -- QA repair feedback carried into repair attempts

    status TEXT NOT NULL DEFAULT 'pending',
    -- allowed: 'pending','executing','review','repair_retry','approved','failed_terminal','skipped'

    assigned_to TEXT DEFAULT 'Engineer',

    result_artifact_ids TEXT,             -- JSON array of artifact IDs produced/used this attempt

    repair_attempt INTEGER NOT NULL DEFAULT 0,

    consumed_tokens INTEGER NOT NULL DEFAULT 0,       -- total tokens for this task across all calls
    repair_budget_spent_usd REAL NOT NULL DEFAULT 0.0,

    tokenizer_model TEXT,                 -- normative tokenizer identifier used for this task's LLM calls

    started_at DATETIME,                  -- immutable snapshot anchor for current attempt
    locked_at DATETIME,
    locked_by TEXT,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    completed_at DATETIME
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_mission_tasks_mission_order
    ON mission_tasks(mission_id, task_order);

CREATE INDEX IF NOT EXISTS idx_mission_tasks_status
    ON mission_tasks(mission_id, status, task_order);

-- Table: artifacts
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),

    -- Project Builder additions
    file_path TEXT,                 -- relative path under workspace; NULL for non-file artifacts
    version_number INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES artifacts(id),
    is_deleted INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true

    -- Other v1.0 columns (unchanged)
    kind TEXT NOT NULL,             -- e.g. "file", "log", "planner_output", etc.
    mime_type TEXT,
    checksum TEXT,                  -- e.g. "sha256:...."
    size_bytes INTEGER,
    content BLOB,                   -- for text artifacts, UTF-8 bytes; for binary artifacts, content may be NULL or out-of-scope storage
    metadata_json TEXT,

    created_at DATETIME NOT NULL
);

-- Deterministic project-state indexes
CREATE INDEX IF NOT EXISTS idx_artifacts_snapshot
  ON artifacts(mission_id, file_path, version_number DESC);

CREATE INDEX IF NOT EXISTS idx_artifacts_project_state
  ON artifacts(mission_id, file_path, created_at DESC, version_number DESC);

CREATE INDEX IF NOT EXISTS idx_artifacts_mission_created
  ON artifacts(mission_id, created_at DESC);

-- Snapshot + required_artifact_ids performance
CREATE INDEX IF NOT EXISTS idx_artifacts_required
  ON artifacts(mission_id, id);

-- Table: timeline_events
CREATE TABLE IF NOT EXISTS timeline_events (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    task_id TEXT REFERENCES mission_tasks(id),
    event_type TEXT NOT NULL,              -- e.g. agent_invoked, state_transition, task_started, ...
    event_json TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_timeline_mission
  ON timeline_events(mission_id, created_at);

CREATE INDEX IF NOT EXISTS idx_timeline_task
  ON timeline_events(task_id, created_at);
