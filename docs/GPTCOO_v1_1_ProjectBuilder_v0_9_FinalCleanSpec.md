# GPTCOO v1.1 – Project Builder  
**Specification v0.9 (Final Clean Implementation Spec, DeepSeek-Compliant)**

This version integrates **all five DeepSeek-required fixes**:
1. Executable SQLite repair-budget transaction.
2. Platform-agnostic lock reclaim liveness check.
3. Explicit tokenizer requirements for non-OpenAI models.
4. Formal enforcement of required_artifact_ids ≤ 3 during plan validation.
5. Deterministic truncation of repair_context (first 2000 Unicode codepoints only).

The remainder of the document is identical to v0.8 unless modified for DeepSeek alignment.

---

## PATCH 1 — Executable SQLite Repair-Budget Update (Replaces §10.3 Pseudo-Code)

The normative budget transaction is now:

```sql
BEGIN IMMEDIATE;

-- 1. Mission budget (always applies)
UPDATE missions
SET spent_cost_usd = spent_cost_usd + :cost
WHERE id = :mid
  AND spent_cost_usd + :cost <= max_cost_usd;

SELECT changes() AS main_ok;

-- 2. Repair budget (conditional)
-- Application logic controls whether this UPDATE executes.
-- Only execute this block if :is_repair_attempt = 1.
UPDATE mission_tasks
SET repair_budget_spent_usd = repair_budget_spent_usd + :cost
WHERE id = :tid
  AND repair_budget_spent_usd + :cost <= (
      SELECT repair_budget_usd FROM missions WHERE id = :mid
  );

SELECT changes() AS repair_ok;

-- Application determines:
-- main_success  = (main_ok   = 1)
-- repair_success = (repair_ok = 1) if is_repair_attempt=1 else True

-- Commit gate in application logic:
-- if main_success AND repair_success: COMMIT
-- else: ROLLBACK
```

This block is **executable SQLite** with correct semantics.

---

## PATCH 2 — Platform-Agnostic Liveness Check (Adds to §6.4)

Replace reclaim step with:

> “The orchestrator MUST verify liveness of the worker identified by `locked_by`.  
> - If `locked_by` is an integer PID and the platform is POSIX, use `os.kill(pid, 0)`.  
> - Otherwise, on non-POSIX systems or if `locked_by` is not a PID, the orchestrator MUST use an equivalent OS-level process existence API.  
> - If liveness cannot be established or `locked_by` is invalid, **reclaim MUST NOT proceed**.  
> - A `timeline_events` row MUST be recorded with `event_type='task_reclaim_skipped_alive_or_unknown'`.”

---

## PATCH 3 — Tokenizer Requirements for Non‑OpenAI Models (Adds to §8.4)

Add the following paragraph:

> “For non‑OpenAI models, the model configuration MUST define a stable tokenizer identifier via a `tokenizer` field (e.g., `'z-tokenizer/glm-4.6-v1'`).  
> COO MUST record this identifier into `mission_tasks.tokenizer_model` **before** any token counting occurs.  
> All context injection and budget token accounting MUST use this recorded tokenizer both during execution and replay.”

---

## PATCH 4 — Enforcement of required_artifact_ids ≤ 3 (Replaces part of §7.4)

Add immediately after the plan validation steps:

> “If any task specifies `required_artifact_ids`, COO MUST parse it as a JSON array and enforce **length ≤ 3**.  
> A violation MUST cause:  
> - Plan rejection,  
> - A `QUESTION` to CEO explaining `required_artifact_ids_limit_exceeded`, and  
> - No tasks inserted for this mission.”

Also:  
“This constraint MUST also be validated on any subsequent writes to mission_tasks.”

---

## PATCH 5 — Deterministic repair_context Truncation (Adds to §6.3)

Add the following deterministic rule:

> “When truncating `repair_context`, COO MUST take exactly the **first 2000 Unicode code points**.  
> No word-boundary logic, normalization changes, or heuristic trimming is allowed.  
> Truncation MUST be recorded via `timeline_events(event_type='repair_context_truncated')`.”

---

# Full v0.9 (v0.8 + DeepSeek Fixes)

The full integrated v0.9 specification follows.  
All modified sections include the DeepSeek patches inline.

---

# GPTCOO v1.1 – Project Builder  
**Specification v0.8 (Final Clean Implementation Spec)**

---

## 1. Scope & Relationship to COO v1.0

1. The **COO v1.0 Spec** defines the core runtime: missions, messages, artifacts, sandbox, budget enforcement, and orchestrator/agent framework.
2. **Project Builder (v1.1)** extends COO v1.0 from **single-file code tasks** to **multi-file project missions** with:
   - Planner-driven linear task decomposition.
   - Deterministic, per-task sandbox workspaces.
   - Multi-file artifact versioning and tombstones.
   - A bounded repair loop per task.
   - Strong per-mission and repair budget governance.
3. Where this spec is **silent**, the COO v1.0 rules apply. Where there is a conflict, this spec is authoritative for **Project Builder missions**.

---

## 2. Architectural Principles & Replayability

### 2.1 Core Principles

1. **Determinism**  
   For any mission, given identical DB state, model configuration, tokenizer, and sandbox image, replaying the mission must yield identical artifact checksums.

2. **Isolation**  
   Each task attempt executes in a fresh sandbox workspace. No filesystem state is shared between tasks or attempts; only database artifacts persist.

3. **Data-First State**  
   Missions, tasks, artifacts, messages, budgets, sandbox_runs, and timeline_events are the single source of truth.

4. **Budget Safety**  
   Every LLM call is checked against per-mission and repair budgets **before** execution and committed atomically with cost accounting **after** execution.

5. **Linear Task Model**  
   Missions are decomposed into a strictly linear sequence of tasks with `task_order = 1..N`. No DAG, no `depends_on`.

6. **Minimal Tool Surface**  
   Agents interact with the world only via:
   - LLM calls,
   - sandbox execution,
   - the artifact store.

7. **Replayability Contract**

Given:

- The same `missions`, `mission_tasks`, `artifacts`, `sandbox_runs`, `budgets_global`, `messages`, and `timeline_events` rows,
- The same model configurations and prompts,
- The same **tokenizer choices recorded per task**, and
- The same sandbox image and entrypoints,

Then:

- Re-materializing snapshots (§4),
- Injecting context (§8),
- Executing tasks in `task_order`,

MUST produce identical artifact checksums for all task attempts.

All non-deterministic sources (random seeds, non-alphabetical traversal, non-normalized paths, tokenizer changes) are forbidden unless explicitly controlled and logged.

---

## 3. Database Schema (Project Builder Extensions)

The Project Builder spec assumes the **COO v1.0 schema** as baseline, including: `missions`, `messages`, `artifacts`, `sandbox_runs`, `dead_letters`, `timeline_events`, `budgets_global`, `models`, etc.

This section defines the **authoritative state** of tables that are extended or newly introduced.

### 3.1 missions

Base v1.0 table (simplified, with v1.1 additions):

```sql
CREATE TABLE missions (
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
CREATE INDEX idx_missions_status ON missions(status);
```

**Project Builder-specific semantics:**

1. `loop_count` and `max_loops` are **not used** by Project Builder missions. The orchestrator:
   - SHALL NOT increment `loop_count` for Project Builder missions, and
   - SHALL ignore `max_loops` for Project Builder missions (looping is modeled via `mission_tasks` and repair attempts).
   For Project Builder missions, `loop_count` is expected to remain `0`.
2. Canonical values for `failure_reason` MUST be one of:
   - `'task_failed'`
   - `'budget_exceeded'`
   - `'repair_budget_exceeded'`
   - `'plan_revision_exhausted'`
   - `'task_backpressure'`
   - `'sandbox_error'`
   - `'sandbox_manifest_error'`
   - `'invalid_artifact_path'`
   - `'manifest_syntax_error'`
   - `'sandbox_checksum_mismatch'`
   - `'sandbox_incomplete_write'`
   - `'required_artifact_ids_limit_exceeded'`
   Additional values MAY be added but SHOULD be documented for CLI/UX.

3. `mission.task_count` IS NOT stored; it is derived as `COUNT(*) FROM mission_tasks WHERE mission_id = ?`.

### 3.2 mission_tasks

```sql
CREATE TABLE mission_tasks (
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

CREATE UNIQUE INDEX idx_mission_tasks_mission_order
    ON mission_tasks(mission_id, task_order);

CREATE INDEX idx_mission_tasks_status
    ON mission_tasks(mission_id, status, task_order);
```

**Normative constraints:**

1. For any mission, `task_order` must be **exactly** `1..N` with no gaps or duplicates.
2. `started_at` is set **once per attempt** when transitioning into `executing` and is never modified for that attempt (§4.2, §5.2).
3. `repair_context` semantics are defined in §6.3.
4. `tokenizer_model` records the tokenizer used to compute token counts and must be used for any replay of that task (§8.4).
5. For any written `required_artifact_ids` value, the COO MUST validate that its JSON array length is ≤ 3 (§4.3, §7.4).

### 3.3 artifacts

Project Builder extends the v1.0 artifacts table. Final schema:

```sql
CREATE TABLE artifacts (
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
CREATE INDEX idx_artifacts_snapshot
  ON artifacts(mission_id, file_path, version_number DESC);

CREATE INDEX idx_artifacts_project_state
  ON artifacts(mission_id, file_path, created_at DESC, version_number DESC);

CREATE INDEX idx_artifacts_mission_created
  ON artifacts(mission_id, created_at DESC);

-- Snapshot + required_artifact_ids performance
CREATE INDEX idx_artifacts_required
  ON artifacts(mission_id, id);
```

**Rules:**

- `file_path` is **authoritative** for project files; prior uses of `path` are obsolete.
- `checksum` MUST be `sha256:<hex>`; bare hashes are invalid (§9.2).
- `is_deleted=1` rows are tombstones and are never materialized into workspaces.
- `required_artifact_ids` MUST contain at most **3** artifact IDs per task; the orchestrator MUST enforce this both:
  - When accepting Planner/CEO input that sets `required_artifact_ids`, and
  - When inserting or updating `mission_tasks` rows.

### 3.4 timeline_events

Final schema:

```sql
CREATE TABLE timeline_events (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    task_id TEXT REFERENCES mission_tasks(id),
    event_type TEXT NOT NULL,              -- e.g. agent_invoked, state_transition, task_started, ...
    event_json TEXT NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE INDEX idx_timeline_mission
  ON timeline_events(mission_id, created_at);

CREATE INDEX idx_timeline_task
  ON timeline_events(task_id, created_at);
```

### 3.5 budgets_global, sandbox_runs, messages (context)

These tables are defined in COO v1.0 and used unchanged by Project Builder, except for semantics clarified in §10.

Key points:

- `budgets_global` tracks daily/monthly global spend caps.
- `sandbox_runs` records idempotent sandbox executions and their result artifacts.
- `messages` implements the durable queue, including new SYSTEM message shapes (§11.3).

---

## 4. Workspace & Snapshot Semantics

### 4.1 Workspace Path Determinism

For each task attempt:

```text
workspace_root = /tmp/coo-{mission_id}-{task_id}-{repair_attempt}
```

- `repair_attempt` is taken from the current `mission_tasks.repair_attempt` integer.
- **Random values (UUIDs, timestamps) are forbidden** in the path.
- Violating this rule breaks determinism and replay.

### 4.2 Immutable Snapshot Anchor (started_at)

1. When a task transitions `pending → executing` or `repair_retry → executing`, the orchestrator must:
   - Set `mission_tasks.started_at = CURRENT_TIMESTAMP`,
   - Set `status = 'executing'`,
   - Set `locked_at = CURRENT_TIMESTAMP`, `locked_by = <worker_id>`,
   - Commit these changes in a single transaction.
2. `started_at` MUST be set **immediately before** workspace materialization begins and in the **same atomic transaction** as the status update to `executing`.
3. `started_at` is never modified for the lifetime of that attempt. Reclaim resets only `locked_at` and `locked_by`.

### 4.3 Snapshot Query (Including required_artifact_ids)

The per-task snapshot is defined as:

> For task `t.id = :task_id` in mission `:mission_id`, at time `t.started_at`, the workspace consists of:
> - The latest non-deleted version of each file whose `created_at <= t.started_at`, plus
> - Any artifacts explicitly referenced in `required_artifact_ids`, even if those artifacts are newer or would otherwise be excluded.

**SQLite-compatible query:**

```sql
-- Inputs:
--   :mission_id
--   :task_id

WITH snapshot_artifacts AS (
  SELECT a.file_path, a.content
  FROM artifacts a
  JOIN mission_tasks t ON t.mission_id = a.mission_id
  WHERE t.id = :task_id
    AND a.mission_id = :mission_id
    AND a.file_path IS NOT NULL
    AND a.is_deleted = 0
    AND a.created_at <= t.started_at
    AND a.version_number = (
      SELECT MAX(a2.version_number)
      FROM artifacts a2
      WHERE a2.mission_id = a.mission_id
        AND a2.file_path = a.file_path
        AND a2.created_at <= t.started_at
    )
),
required_artifacts AS (
  SELECT a.file_path, a.content
  FROM artifacts a
  WHERE a.mission_id = :mission_id
    AND a.id IN (
      SELECT value
      FROM json_each(
        (
          SELECT required_artifact_ids
          FROM mission_tasks
          WHERE id = :task_id
            AND required_artifact_ids IS NOT NULL
            AND json_valid(required_artifact_ids) = 1
        )
      )
    )
    AND a.is_deleted = 0
)
SELECT * FROM required_artifacts
UNION
SELECT * FROM snapshot_artifacts
WHERE file_path NOT IN (SELECT file_path FROM required_artifacts)
ORDER BY file_path ASC;
```

Notes:

1. `required_artifact_ids` is a JSON array column on `mission_tasks` and is optional; if it is NULL or invalid JSON, `required_artifacts` is empty.
2. `required_artifact_ids` MUST contain at most **3** IDs per task to avoid performance and timeout issues; the COO MUST enforce this at the point of writing `mission_tasks.required_artifact_ids` (see §7.4).
3. When an artifact appears in both sets, the `required_artifacts` version wins.
4. Files are returned lexicographically by `file_path`. All file tree and context builders must preserve this order.
5. The `idx_artifacts_required` index (`mission_id, id`) MUST be present to keep required-artifact lookups bounded.
6. **SQLite JSON1 requirement:** This query requires SQLite compiled with the JSON1 extension (i.e., support for `json_each` and `json_valid`). Most modern SQLite distributions used in application runtimes include this by default.

### 4.4 Materialization Rules

When materializing a snapshot to `workspace_root`:

1. For each row `(file_path, content)`:
   - Normalize `file_path` to ensure:
     - It does not start with `/`.
     - It does not contain `..` segments.
     - It uses **only forward slashes (`/`)**; any path containing backslashes `\` is invalid.
   - Compute the resolved path under `workspace_root`. If resolution escapes `workspace_root`, treat as invalid (security violation).
2. If a path is invalid under these rules:
   - The task transitions to `failed_terminal` with `reason = 'invalid_artifact_path'`.
   - A `timeline_events` row is added with details.
3. Files are written as:
   - UTF-8 text with **LF** (`\n`) line endings (normalize CRLF).
   - File mode `0644`.
4. Symlinks in the workspace are forbidden:
   - If the sandbox writes symlinks, treat as `sandbox_invalid_symlink` and transition task to `failed_terminal`.

### 4.5 Workspace Cleanup & Reclaim

- On normal completion of a task attempt (approved / failed_terminal / skipped), orchestrator deletes `workspace_root`.
- On reclaim of a stale task, orchestrator deletes the previous workspace for that attempt before rerunning (§5.4).
- Periodic cleanup may remove stale directories older than 24 hours.

---

## 5. Task Model & FSM

### 5.1 States

`mission_tasks.status ∈ { 'pending','executing','review','repair_retry','approved','failed_terminal','skipped' }`

### 5.2 State Transitions

**Message–Transition Table**

| Transition                     | From → To          | Trigger Message                  | Sender → Receiver |
|--------------------------------|--------------------|----------------------------------|-------------------|
| Start execution                | pending → executing     | TASK                             | COO → Engineer    |
| Send result for review         | executing → review      | RESULT                           | Engineer → COO    |
| Approve                        | review → approved       | APPROVAL (decision=approved)     | QA → COO          |
| Request repair                 | review → repair_retry   | APPROVAL (decision=repair_suggested) | QA → COO    |
| Start repair execution         | repair_retry → executing| TASK (repair attempt)            | COO → Engineer    |
| Final rejection from review    | review → failed_terminal| APPROVAL (decision=rejected)     | QA → COO          |
| Sandbox/infra fatal failure    | executing → failed_terminal| SYSTEM/ERROR from orchestrator | Orchestrator → COO|
| Reclaim stale execution        | executing → pending     | Internal reclaim logic           | Orchestrator      |

**Rules:**

1. All LLM-facing messages flow **through COO**. No direct Engineer↔QA, Planner↔Engineer, or QA↔Engineer messaging is allowed (§11.2).
2. A task in `failed_terminal` is terminal for that task; it will never re-enter `pending`, `executing`, or `review` for that attempt.
3. On the `repair_retry → executing` transition, the orchestrator MUST:
   - Set a **new** `started_at` timestamp per §4.2.
   - Allocate a new workspace directory based on the updated `repair_attempt` value.
   - Keep `repair_context` unchanged (it is updated only on `review → repair_retry`).

### 5.3 Mission-Level Failure Propagation

When any task transitions to `failed_terminal`, orchestrator must:

```sql
BEGIN IMMEDIATE;

UPDATE missions
SET status = 'failed',
    failure_reason = 'task_failed'
WHERE id = :mid;

UPDATE mission_tasks
SET status = 'skipped'
WHERE mission_id = :mid
  AND status IN ('pending','repair_retry');

COMMIT;
```

Also:

- Insert `timeline_events` with `event_type='mission_failed'`, `task_id = failing_task_id`.

### 5.4 Lock Reclamation

A task is **stale** if:

```text
status = 'executing' AND locked_at < now - TASK_LOCK_TIMEOUT_SECONDS
```

(`TASK_LOCK_TIMEOUT_SECONDS` configurable, default 600 seconds.)

Reclaim process:

1. The orchestrator MUST verify whether the worker process identified by `locked_by` is still alive:
   - On POSIX systems, via `os.kill(pid, 0)` or equivalent.
   - On other systems, using the platform-equivalent liveness check.
   - If the process is still alive, reclaim is **forbidden**; the orchestrator MUST:
     - Skip reclaim for this task,
     - Log a warning (e.g., to `timeline_events` with `event_type='task_reclaim_skipped_alive'`).
2. If the process is not alive (or `locked_by` is invalid), in a single transaction:
   ```sql
   BEGIN IMMEDIATE;
   UPDATE mission_tasks
   SET status = 'pending',
       locked_at = NULL,
       locked_by = NULL
   WHERE id = :task_id;
   COMMIT;
   ```
3. Delete the previous workspace for that attempt.
4. Insert `timeline_events` with `event_type='task_reclaimed'`.

`started_at` and `repair_attempt` are **not** modified during reclaim.

---

## 6. QA, Repair Loop & repair_context

### 6.1 QA APPROVAL Message Schema

QA sends APPROVAL messages of the form:

```json
{
  "kind": "APPROVAL",
  "from_agent": "QA",
  "to_agent": "COO",
  "mission_id": "<mid>",
  "body_json": {
    "artifact_type": "qa_approval",
    "task_id": "t2",
    "decision": "approved" | "repair_suggested" | "rejected",
    "repair_suggestion": "Fix failing test in tests/test_main.py",
    "repair_context": "Human-readable and structured repair instructions...",
    "reason": "test_failed" | "import_error" | "code_quality" | "...",
    "issues": [
      { "file": "tests/test_main.py", "line": 42, "issue": "Assertion error ..." }
    ],
    "test_output_artifact_id": "<artifact_id_or_null>"
  }
}
```

**Rules:**

- `decision` must be one of the three enumerated values.
- If `decision != 'approved'`, `test_output_artifact_id` SHOULD be non-null so QA evidence can be inspected.

### 6.2 Repair Policy & Limits

Config:

- `MAX_REPAIRS_PER_TASK = 1` (default, configurable).
- `repair_budget_usd` on missions is a **spend cap**, not a reserved pool (§10.2).

Policy:

1. If `decision = 'repair_suggested'` and `repair_attempt < MAX_REPAIRS_PER_TASK`:
   - Task state: `review → repair_retry`.
   - Increment `repair_attempt += 1`.
   - Update `repair_context` with QA feedback (§6.3).
   - COO will later send a repair TASK to Engineer.
2. If `decision = 'repair_suggested'` and `repair_attempt >= MAX_REPAIRS_PER_TASK`:
   - Treat as `rejected`: `review → failed_terminal`.
3. After a repair attempt, QA sends a final APPROVAL (`approved` or `rejected`).

### 6.3 repair_context Lifecycle

`mission_tasks.repair_context` carries QA feedback into Engineer repair prompts.

**When set:**

- On `review → repair_retry` transition:
  - COO sets `mission_tasks.repair_context` to a serialized string that *must* include:
    - QA’s `repair_suggestion`.
    - A concise summary of `issues[]` and test artifacts.
  - This update is transactionally tied to the state transition.
  - Before writing to the database, COO MUST:
    - Truncate `repair_context` to at most **2000 Unicode characters**.
    - If truncation occurs, insert a `timeline_events` row with `event_type='repair_context_truncated'` and enough detail to debug.

**When used:**

- On `repair_retry → executing`:
  - COO includes `repair_context` verbatim (already truncated if needed) in the Engineer’s prompt for that task.
  - `repair_context` must be part of explicit token accounting (§8.4).

**When cleared:**

- On `review → approved` or `review/repair_retry → failed_terminal`:
  - COO sets `repair_context = NULL` for that task.

### 6.4 Repair Budget Accounting

See §10.2–§10.3 for full transaction semantics. At a high level:

- All LLM calls (normal and repair) are charged against `missions.spent_cost_usd`.
- Repair LLM calls also increment `mission_tasks.repair_budget_spent_usd`.

---

## 7. Planner / COO / CEO Protocol

### 7.1 Planner Role

- Receives mission description and constraints from COO.
- Proposes a **linear plan** of tasks.
- Optionally suggests `context_files` per task.
- MAY propose `required_artifact_ids` assignments indirectly (e.g., via CEO/COO instructions), but the COO is ultimately responsible for enforcing the hard limit (§3.2, §4.3).

### 7.2 Planner Output

Planner’s conceptual output:

```json
{
  "tasks": [
    {
      "id": "t1",
      "description": "Scaffold a basic FastAPI app structure",
      "context_files": []
    },
    {
      "id": "t2",
      "description": "Add CRUD endpoints for Item model",
      "context_files": ["src/models.py"]
    }
  ],
  "estimated_total_tokens": 18000,
  "estimated_cost_usd": 3.50
}
```

Constraints:

- Task IDs must be exactly `"t1"..."tN"`, sequential with no gaps.
- `context_files` are optional relative paths; invalid paths are allowed but treated as hints only (see below).

### 7.3 PLAN Message (Planner → COO)

Planner sends a PLAN as:

```json
{
  "kind": "PLAN",
  "from_agent": "Planner",
  "to_agent": "COO",
  "mission_id": "<mid>",
  "in_reply_to": "<original_TASK_id>",
  "body_json": {
    "artifact_type": "planner_output",
    "tasks": [...],
    "estimated_total_tokens": 18000,
    "estimated_cost_usd": 3.50
  }
}
```

### 7.4 COO Plan Validation & CEO Interaction

Config defaults:

- `MAX_TASKS_PER_MISSION = 5`
- `PLANNER_BUDGET_FRACTION = 0.8` (planner’s estimate must be ≤ 80% of mission budget)
- `MAX_PLAN_REVISIONS = 3`

Validation algorithm:

1. Basic checks:
   - `1 <= len(tasks) <= MAX_TASKS_PER_MISSION`.
   - `tasks[i].id == "t{i+1}"` for `i=0..N-1`.
2. Budget:
   - `estimated_cost_usd <= missions.max_cost_usd * PLANNER_BUDGET_FRACTION`.
3. `required_artifact_ids` limit:
   - If Planner or CEO proposes any `required_artifact_ids` values (e.g., via mission config or subsequent control messages), the COO MUST:
     - Parse them as JSON arrays,
     - Enforce `len(required_artifact_ids) <= 3` per task.
   - If any task violates this limit:
     - Reject the plan or update,
     - Set `missions.failure_reason = 'required_artifact_ids_limit_exceeded'` if it is fatal, and/or
     - Send a `QUESTION` to CEO explaining the violation.
4. Context sanity:
   - `context_files` entries are strings; invalid paths are allowed but treated as hints only.
5. Planner LLM budget charging:
   - All Planner LLM calls used to generate or revise the plan MUST:
     - Be charged against `missions.spent_cost_usd` using the same budget transaction pattern as §10.3.
     - Be included when evaluating `PLANNER_BUDGET_FRACTION`. If Planner calls alone would cause `spent_cost_usd` to exceed `max_cost_usd * PLANNER_BUDGET_FRACTION`, the COO MUST:
       - Reject the plan,
       - Optionally send a `QUESTION` to CEO.

If validation **passes**:

- Insert `mission_tasks` rows with:
  - `id` from Planner (`t1..tN`).
  - `task_order` equal to numeric suffix.
  - `description`, `context_files`.
- Set `missions.status = 'executing'`.
- Insert `timeline_events` with `event_type='planner_decomposed'`.

If validation **fails**:

- COO sends a `QUESTION` to CEO:
  ```json
  {
    "kind": "QUESTION",
    "from_agent": "COO",
    "to_agent": "CEO",
    "mission_id": "<mid>",
    "body_json": {
      "reason": "plan_validation_failed",
      "errors": [...],
      "proposed_actions": [...]
    }
  }
  ```
- CEO responds with a `RESULT` to Planner via COO, typically:
  ```json
  {
    "kind": "RESULT",
    "from_agent": "CEO",
    "to_agent": "COO",
    "mission_id": "<mid>",
    "body_json": {
      "action": "revise_plan",
      "constraints": { ... }
    }
  }
  ```
- COO forwards this as a `TASK` to Planner.
- Increment `missions.plan_revision_count`.
- If `plan_revision_count > MAX_PLAN_REVISIONS`, set:
  - `missions.status = 'failed'`
  - `failure_reason = 'plan_revision_exhausted'`.

### 7.5 context_files Usage

- `context_files` are treated as **highest priority** context candidates (Bucket A, §8.2).
- If `context_files` entries are invalid (paths not found in snapshot):
  - COO logs a warning in `timeline_events` but continues.
  - Invalid paths do not cause task failure.

---

## 8. Context Injection & Token Accounting

### 8.1 Prompt Components

For an Engineer call on a given task, the prompt MUST be composed of:

1. System prompt for Engineer.
2. Mission description and high-level config.
3. Task description (including whether it is a repair).
4. `repair_context` (if non-null).
5. File tree listing for the snapshot.
6. Selected file contents (see buckets below).
7. Relevant QA feedback / test logs.
8. Any additional mission/task config required by models.

### 8.2 Priority Buckets

1. **Bucket A (Priority)**: all snapshot files whose `file_path` is listed in `mission_tasks.context_files`.
2. **Bucket B (Recency)**: all other snapshot files, sorted by:
   - `created_at DESC`, then
   - `file_path ASC`.

Bucket B must **exclude** all Bucket A files. Files in Bucket A are never duplicated.

### 8.3 File Selection Algorithm

Config:

- `MAX_FILE_TREE_TOKENS` (e.g. 500).
- `MAX_ARTIFACT_TOKENS` (e.g. 2000) — tokens available for file contents.

Algorithm:

1. Compute tokens for:
   - system prompt,
   - mission + task descriptions,
   - `repair_context`,
   - QA feedback (if any),
   - file tree.
   Call this `base_tokens`.
2. Remaining budget for file contents: `remaining = MAX_ARTIFACT_TOKENS - base_tokens`.
3. For each file in **Bucket A** then **Bucket B**:
   - If `remaining <= 0`: stop.
   - Compute `file_tokens` for full content.
   - If `file_tokens <= remaining`:
     - Inject full content.
     - `remaining -= file_tokens`.
   - Else:
     - Truncate at line boundaries to fit `remaining`.
     - Append marker:
       ```text
       # [...TRUNCATED BY COO...]
       ```
     - Inject truncated content and stop.

### 8.4 Token Counting Determinism

1. Token counting must use a **normatively defined tokenizer**:
   - For all OpenAI GPT-4-class models (e.g., GPT-4, GPT-4.1, GPT-4o), the tokenizer MUST be:
     - `tiktoken` with the `cl100k_base` encoding (or the official successor encoding explicitly listed in the model config).
   - For non-OpenAI models, the orchestrator MUST:
     - Declare an explicit tokenizer identifier for the model in the model configuration (e.g., `"tokenizer": "z-tokenizer/glm-4.6"`).
2. Components must be counted in a fixed order:
   1. System prompt.
   2. Mission + task description.
   3. `repair_context` (if any).
   4. File tree.
   5. QA feedback/test logs.
   6. Each file in bucket order.
3. For each Engineer or QA LLM call on a given task:
   - BEFORE performing any token counting for context injection or budget checks, the orchestrator MUST:
     - Choose the tokenizer according to the model’s configuration, and
     - Set `mission_tasks.tokenizer_model` to a stable identifier string (e.g., `"tiktoken/cl100k_base"`, `"z-tokenizer/glm-4.6"`).
   - All subsequent token counting for that task attempt MUST use `mission_tasks.tokenizer_model`.
   - On replay, the orchestrator MUST reuse `mission_tasks.tokenizer_model` and MUST NOT switch to a different tokenizer, even if defaults change.
4. The same tokenizer and ordering must be used across runs on the same mission for determinism.
5. Planner’s tokenizer is **not** recorded in `mission_tasks` because Planner output is captured as artifacts and is not re-generated on replay; replay consumes Planner artifacts directly instead of re-running Planner LLM calls.
6. (Recommended) For debugging, log context token usage to `timeline_events` with `event_type='context_tokens'` and a summary of token counts per component.

---

## 9. Manifest & Artifact Ingestion

### 9.1 Canonical Manifest Source

To eliminate non-determinism from stdout:

- The sandbox MUST write a manifest file at:
  ```text
  /workspace/.coo-manifest.json
  ```
- The orchestrator MUST read **only** this file.
- Stdout may contain arbitrary logs; it is ignored for manifest purposes.

### 9.2 Manifest Schema

```json
{
  "manifest_version": 1,
  "files": [
    {
      "path": "src/main.py",
      "checksum": "sha256:abc123...",
      "deleted": false
    }
  ],
  "exit_code": 0,
      "error": null
}
```

Rules:

- `path`:
  - No leading `/`.
  - No `..` components.
  - **Must use `/`** (forward slashes only); any `\` path is rejected.
- `checksum`:
  - Must start with `"sha256:"`; bare hashes are rejected.
- `deleted`:
  - Boolean.
  - Maps to `artifacts.is_deleted` (true → 1, false → 0).
- `exit_code`:
  - The sandbox process exit code.
- `error`:
  - Optional human-readable error description.

### 9.3 Manifest Missing / Invalid

If `.coo-manifest.json` is:

- Missing,
- Unreadable, or
- Not valid JSON,

Then:

- The task transitions to `failed_terminal`,
- With `reason = 'sandbox_manifest_error'`,
- A `timeline_events` row is inserted describing the parse failure.

If JSON is valid but fields are invalid (e.g., bad checksum format, illegal path), treat as `invalid_artifact_path` or `manifest_syntax_error` as appropriate and fail terminally.

### 9.4 Artifact Ingestion Algorithm

For each `f` in `manifest.files`:

1. Validate `f.path` per §4.4 and §9.2. If invalid, task fails terminal (`invalid_artifact_path`).
2. Look up latest artifact for `(mission_id, f.path)`:

   ```sql
   SELECT id, checksum, version_number, is_deleted
   FROM artifacts
   WHERE mission_id = :mid
     AND file_path = :path
   ORDER BY version_number DESC
   LIMIT 1;
   ```

3. If `f.deleted == true`:

   - If no latest artifact:
     - Insert a tombstone:
       - `version_number = 1`
       - `supersedes_id = NULL`
       - `is_deleted = 1`
       - `content = NULL`
   - If latest exists and `is_deleted = 1`:
     - **No-op** (no new artifact).
   - If latest exists and `is_deleted = 0`:
     - Insert tombstone:
       - `version_number = latest.version_number + 1`
       - `supersedes_id = latest.id`
       - `is_deleted = 1`
       - `content = NULL`.

4. If `f.deleted == false`:

   - Confirm the file exists in `workspace_root` at `f.path`; if not, fail terminal (`sandbox_incomplete_write`).
   - Read file content, normalize to UTF-8 + LF.
   - Normalize line endings before computing checksum.
   - Compute SHA-256; ensure matches `f.checksum`.
     - If mismatch, fail terminal with `reason = 'sandbox_checksum_mismatch'`.
   - If latest exists and `latest.is_deleted=0` and `latest.checksum == f.checksum`:
     - **No-op** (reuse existing artifact ID).
   - Else insert new artifact:
     - `version_number = latest.version_number + 1` or `1` if none.
     - `supersedes_id = latest.id` or `NULL`.
     - `is_deleted = 0`.
     - `file_path = f.path`.
     - `content` = file bytes.

5. After processing all files:
   - Collect IDs of all artifacts that represent the **effective state** of each `f.path` in this attempt. For unchanged files, this includes existing artifact IDs.
   - Set `mission_tasks.result_artifact_ids` to a JSON array of these IDs (the manifest’s scope, not the entire project).

---

## 10. Budget & Backpressure

### 10.1 Global Budget (budgets_global)

Global daily/monthly budget semantics are inherited from COO v1.0.

### 10.2 Mission Budget & Repair Budget

**Conceptual rules:**

1. `max_cost_usd` is the **hard cap** on all LLM calls in a mission.
2. `repair_budget_usd` is a **spend cap** for repair attempts only. It is not a reserved pool:
   - Normal tasks may consume up to the entire `max_cost_usd`.
   - Repairs can only occur if there is room under both:
     - `(max_cost_usd - spent_cost_usd)`, and
     - `repair_budget_usd - (SUM of repair spend)`.

3. All LLM calls increment `missions.spent_cost_usd`.
4. Repair LLM calls also increment `mission_tasks.repair_budget_spent_usd`.

### 10.3 Atomic Budget Transaction (Normative SQLite Pattern)

Budget enforcement MUST be wrapped in a single SQL transaction. Use `BEGIN IMMEDIATE` to acquire a write lock and avoid race conditions. **Engineers MUST NOT split mission and repair budget updates into separate transactions.**

Normative pattern for a single LLM call costing `:cost` on mission `:mid` and task `:tid`:

```sql
BEGIN IMMEDIATE;

-- 1. Main mission budget (always applies)
UPDATE missions
SET spent_cost_usd = spent_cost_usd + :cost
WHERE id = :mid
  AND spent_cost_usd + :cost <= max_cost_usd;

SELECT changes() AS main_ok;
-- Application: main_success = (main_ok = 1)

-- 2. Repair budget (conditional, in same transaction)
-- Application logic (pseudo):
--   repair_success = 1
--   if :is_repair_attempt = 1:
--       UPDATE mission_tasks
--       SET repair_budget_spent_usd = repair_budget_spent_usd + :cost
--       WHERE id = :tid
--         AND repair_budget_spent_usd + :cost <= (
--             SELECT repair_budget_usd FROM missions WHERE id = :mid
--         );
--       SELECT changes() AS repair_ok;
--       repair_success = (repair_ok = 1);

-- (The actual UPDATE and SELECT for repair are executed only when :is_repair_attempt = 1)

-- 3. Commit Gate (performed in application logic)
--   if main_success AND repair_success:
--       COMMIT;
--   else:
--       ROLLBACK;
```

If the transaction is rolled back:

- No budget fields are updated.
- The orchestrator must:
  - Not perform the LLM call,
  - Transition the task to `failed_terminal`,
  - Set `missions.status='failed'` with:
    - `failure_reason = 'budget_exceeded'` (main budget) or
    - `failure_reason = 'repair_budget_exceeded'` (repair cap),
  - Emit a SYSTEM message to CEO (§10.4).

### 10.4 Budget Exhaustion SYSTEM Message

When a mission’s main or repair budget is exhausted and this blocks further progress, COO must send a SYSTEM message to CEO:

```json
{
  "kind": "SYSTEM",
  "from_agent": "COO",
  "to_agent": "CEO",
  "mission_id": "<mid>",
  "body_json": {
    "system_event": "budget_exhausted",
    "budget_type": "mission" | "repair",
    "remaining_budget_usd": 0.0,
    "failed_task_id": "t2",
    "suggestion": "Mission cannot continue due to budget constraints"
  }
}
```

### 10.5 Backpressure

Definitions:

- `pending = COUNT(messages WHERE mission_id=:mid AND status='pending')`
- `BASE_PENDING_LIMIT = 50`
- `MAX_PENDING_PER_TASK = 10`
- `task_count = COUNT(*) FROM mission_tasks WHERE mission_id=:mid`

`max_pending_total = MAX(BASE_PENDING_LIMIT, task_count * MAX_PENDING_PER_TASK)`

Rules:

1. If `pending > max_pending_total`:
   - Set mission `status='paused_error'`,
   - Set `failure_reason='task_backpressure'` (temporarily).
2. While a mission is in a paused status, the scheduler MUST:
   - Not enqueue new TASK messages for that mission.
   - Leave existing `mission_tasks` statuses unchanged (e.g., `repair_retry` stays `repair_retry`).
3. Once `pending < max_pending_total * 0.6`:
   - Auto-resume mission by restoring previous non-paused status.
   - On resume, any tasks in `repair_retry`:
     - MUST retain their `repair_attempt` and `repair_context`,
     - MUST follow the same `repair_retry → executing` path defined in §5.2 (with new `started_at` per §4.2) when scheduled next.

Backpressure pause/resume MUST NOT clear `repair_context` or otherwise disrupt the repair loop.

---

## 11. Messaging Protocol & Routing

### 11.1 Message Kinds (Summary)

Project Builder reuses COO v1.0 message kinds, plus PLAN and additional SYSTEM semantics:

- `TASK`
- `RESULT`
- `STREAM`
- `ERROR`
- `APPROVAL`
- `SANDBOX_EXECUTE`
- `CONTROL`
- `QUESTION`
- `SYSTEM`
- `PLAN` (Planner → COO)

Message envelope structure follows COO v1.0.

### 11.2 Routing Rules (Normative)

All LLM-originated messages MUST be routed through COO:

- Planner → COO → (DB / mission_tasks only)
- Engineer → COO → QA
- QA → COO → Engineer (via TASK for repair)
- CEO ↔ COO (QUESTIONS / RESULT / CONTROL)

Forbidden direct routes:

- Planner → Engineer
- Engineer → QA
- QA → Engineer
- Planner → CEO

### 11.3 SANDBOX_EXECUTE Messages

Sandbox execution uses `SANDBOX_EXECUTE` messages with body:

```json
{
  "artifact_id": "art_123",
  "entrypoint": "python main.py",
  "timeout": 300,
  "dedupe_id": "msg_001",
  "reply_to": "COO"
}
```

Orchestrator enforces:

- Idempotency via `sandbox_runs.dedupe_id`.
- Security: `--network none`, non-root, resource limits, pre-baked image only.

---

## 12. Timeline & Observability

### 12.1 Event Types

Important `timeline_events.event_type` values for Project Builder:

- `planner_decomposed`  
  `{ "task_count": N, "estimated_cost_usd": 3.50 }`
- `task_started`  
  `{ "task_id": "t2" }`
- `task_result_ready`  
  `{ "task_id": "t2", "result_artifact_ids": ["a123","a124"] }`
- `task_approved`  
  `{ "task_id": "t2" }`
- `task_repair_requested`  
  `{ "task_id": "t2", "attempt": 1 }`
- `task_failed`  
  `{ "task_id": "t2", "reason": "timeout|budget_exceeded|..." }`
- `task_reclaimed`  
  `{ "task_id": "t2" }`
- `task_reclaim_skipped_alive`  
  `{ "task_id": "t2", "locked_by": 12345 }`
- `mission_failed`  
  `{ "task_id": "t2", "reason": "task_failed|plan_revision_exhausted|..." }`
- `context_tokens` (optional debug)  
  `{ "task_id": "t2", "system": 200, "file_tree": 100, "files": 1700 }`
- `repair_context_truncated`  
  `{ "task_id": "t2", "original_length": 3500, "truncated_to": 2000 }`

### 12.2 CLI (Informative)

Recommended CLI commands:

- `coo mission <id> tasks` – show tasks with order, status, repair_attempt, repair_context presence, tokenizer_model.
- `coo mission <id> artifacts` – show project state and versions.
- `coo mission <id> timeline` – show mission timeline.

---

## 13. Acceptance Criteria (Project Builder v1.1)

A Project Builder implementation is considered correct if it satisfies:

1. **Planner Decomposition**
   - Given a mission “Build a multi-file FastAPI app with tests”, Planner produces a valid PLAN with `1 ≤ tasks ≤ MAX_TASKS_PER_MISSION`.
   - COO validates and creates `mission_tasks` with contiguous `task_order`.

2. **Sequential Execution**
   - Tasks run strictly in `task_order`.
   - Each task’s workspace snapshot matches DB state up to its `started_at` plus `required_artifact_ids`.

3. **Repair Loop**
   - At least one task fails initial QA due to a deliberate bug and enters `repair_retry`.
   - QA’s `repair_context` is persisted (with truncation if needed) and used.
   - After a single repair attempt, QA approves or rejects and the FSM behaves as specified.

4. **Artifact Management**
   - Manifest ingestion produces correct artifact histories, with:
     - Versioned updates,
     - Tombstones,
     - Deterministic snapshots.
   - Replaying the mission yields identical artifact checksums.

5. **Budget & Backpressure**
   - Missions never exceed `max_cost_usd`.
   - Repair attempts respect `repair_budget_usd` cap.
   - Planner LLM calls are charged to `missions.spent_cost_usd` and respect `PLANNER_BUDGET_FRACTION`.
   - When budgets are exhausted, SYSTEM messages to CEO are emitted with correct schema.
   - Backpressure logic pauses and resumes missions as defined, without breaking the repair loop.
   - All mission- and repair-budget updates occur inside a single `BEGIN IMMEDIATE` transaction with commit gating.

6. **Determinism & Security**
   - Workspaces use deterministic paths.
   - `started_at` is immutable per attempt and used correctly in snapshot queries.
   - Path validation prevents escapes and symlinks.
   - Manifests are file-only; stdout parsing is unused.
   - Tokenization uses a stable tokenizer per task, recorded in `tokenizer_model`, and is reused for any replay.
   - Snapshot queries use the JSON1 extension where required.

This v0.8 specification incorporates all remaining council-required fixes and is intended to be LOCKED for implementation.
