# Antigravity Implementation Packet v0.9.7

*GPTCOO v1.1 Project Builder – Executable Implementation Guide aligned to Spec v0.9*

This packet is the **engineering contract** for implementing the GPTCOO v1.1 Project Builder according to the **v0.9 Final Clean Spec (DeepSeek-compliant)**.

It translates every normative “MUST” in the spec into concrete implementation rules, code-level patterns, tests, and delivery phases suitable for a **junior engineer** under review, under explicit **version control and release management rules**.

-----

## 0\. Source of Truth, Patches & Versioning

### 0.1 Primary Spec

  * **Authoritative spec:** `GPTCOO_v1_1_ProjectBuilder_v0_9_FinalCleanSpec.md`
  * Nothing in this packet overrides the spec. If any conflict is detected, the spec wins and this packet must be updated via PR.

### 0.2 Implementation Packet Versioning

  * This document: **Antigravity Implementation Packet v0.9.7**
  * It corresponds to **Spec v0.9** of GPTCOO v1.1 Project Builder.
  * Git tagging convention:
      * `spec/project-builder-v0.9` – tag on commit containing the locked spec.
      * `impl/project-builder-v0.9.7` – tag on commit where this packet and the compliant implementation are merged to `main`.

Any change to this packet MUST:

1.  Be done via a Git branch: `chore/impl-packet-v0.9.x`.
2.  Be reviewed and approved by a senior / council proxy.
3.  Result in a new version suffix and corresponding Git tag.

### 0.3 Five Critical Spec Patches (v0.8 → v0.9)

Implementation MUST explicitly honor these five DeepSeek-driven patches (already integrated into the spec, repeated here as **Critical Engineering Rules**):

1.  **Budget SQL (Patch 1)**

      * Use `BEGIN IMMEDIATE` with **two-step UPDATE** pattern in SQLite for mission and repair budgets.
      * No Python-side “check-then-update” logic is allowed.

2.  **Lock Reclaim Liveness (Patch 2)**

      * `locked_by` liveness must be checked with **platform-appropriate process existence logic**.
      * Reclaim is forbidden if the worker is still alive or liveness is unknown.

3.  **Tokenizer Recording (Patch 3)**

      * `mission_tasks.tokenizer_model` MUST be recorded **before any token counting or LLM call** per task attempt.
      * Non-OpenAI models must declare a stable tokenizer identifier.

4.  **required\_artifact\_ids Limit (Patch 4)**

      * Any `required_artifact_ids` JSON array MUST have length `≤ 3`.
      * Violation → plan rejection + CEO QUESTION + timeline event.

5.  **repair\_context Truncation (Patch 5)**

      * `repair_context` MUST be truncated to the **first 2000 Unicode code points**, no word-level heuristics.
      * Truncation MUST be logged in `timeline_events`.

These five items are treated as **Critical Engineering Rules**. Any implementation that diverges is non-compliant.

-----

## 1\. Repository Structure

All code for the Project Builder MUST live under a single Git repository with at least the following structure:

```text
/.
├── coo_core/                     # Existing COO v1.0 runtime (imported, not modified here)
│   └── ...
├── project_builder/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py           # Constants: PLANNER_BUDGET_FRACTION, etc.
│   ├── database/
│   │   ├── __init__.py
│   │   ├── schema.sql            # DDL consistent with spec v0.9
│   │   ├── migrations.py
│   │   ├── snapshot.py           # snapshot_query(mid, tid) implementation
│   │   └── timeline.py           # helpers for timeline_events
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── fsm.py                # state transitions
│   │   ├── budget_txn.py         # BEGIN IMMEDIATE budget transaction
│   │   ├── reclaim.py            # lock reclaim + liveness check
│   │   ├── routing.py            # CEO/Planner/Engineer/QA message routing
│   │   └── missions.py           # mission lifecycle, backpressure, failure propagation
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py            # PLAN generation and validation logic
│   │   ├── engineer.py           # task execution orchestration with sandbox
│   │   └── qa.py                 # QA evaluation, repair suggestions
│   ├── context/
│   │   ├── __init__.py
│   │   ├── tokenizer.py          # tokenizer selection logic (pure)
│   │   ├── injection.py          # bucket A/B context construction
│   │   ├── truncation.py         # deterministic truncation markers logic
│   ├── sandbox/
│   │   ├── __init__.py
│   │   ├── runner.py             # Docker/run invocation, exit codes
│   │   ├── manifest.py           # .coo-manifest.json parsing & validation
│   │   ├── security.py           # path normalization, symlink detection, checksum, LF normalization
│   │   └── workspace.py          # workspace materialization and cleanup
│   └── cli/
│       ├── __init__.py
│       └── main.py               # CLI: debug mission, replay, inspect timeline
├── tests/
│   ├── test_schema.py
│   ├── test_snapshot.py
│   ├── test_budget_txn.py
│   ├── test_fsm.py
│   ├── test_planner_validation.py
│   ├── test_repair_context.py
│   ├── test_required_artifact_ids.py
│   ├── test_tokenizer_replay.py
│   ├── test_sandbox_security.py
│   └── test_end_to_end.py
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── docs/
    ├── GPTCOO_v1_1_ProjectBuilder_v0_9_FinalCleanSpec.md
    ├── Implementation_Packet_v0_9_7.md
    └── CHANGELOG.md
```

This structure is **normative** for this implementation.

-----

## 2\. Technology Stack & Environment

  * **Language:** Python 3.10+
  * **Database:** SQLite 3 with JSON1 enabled
  * **Container Runtime:** Docker or containerd, with:
      * `--network=none`
      * `--cap-drop=ALL`
      * `--security-opt=no-new-privileges`
  * **OS Targets:** Linux (primary), with lock-reclaim fallback paths for non-POSIX if needed.

**JSON1 Verification:**
On startup, the module MUST verify SQLite JSON1 availability:

```python
def verify_json1(conn):
    cur = conn.execute("SELECT json_valid('[1]')")
    if cur.fetchone()[0] != 1:
        raise RuntimeError("SQLite JSON1 extension is required")
```

Call `verify_json1()` at module import or first DB connection.

-----

## 3\. Determinism Constraints (Operational Contract)

The following constraints MUST be enforced everywhere:

1.  **No randomness**

      * No `random`, `uuid.uuid4`, non-seeded PRNGs in any critical path.
      * Any necessary randomness (if ever allowed) must be fully seeded and logged, but v1.1 aims for none.

2.  **Deterministic workspace paths**

      * Use **exactly**:
        ```text
        /tmp/coo-{mission_id}-{task_id}-{repair_attempt}
        ```
      * No use of `mkdtemp`, timestamps, or other non-deterministic components.

3.  **Immutable `started_at` per attempt**

      * Set `started_at` once when a task transitions to `executing` or retry-executing.
      * Never update `started_at` thereafter. Reclaim preserves `started_at`.

4.  **Tokenization**

      * `mission_tasks.tokenizer_model` MUST be set **before** computing token counts or sending LLM requests.
      * Replay MUST re-use the recorded tokenizer.

5.  **Context injection ordering**
    Context construction MUST follow the order from the spec:

    1.  System prompt
    2.  Mission + task description
    3.  `repair_context` (if any)
    4.  File tree string
    5.  QA feedback (if any)
    6.  Bucket A files (priority)
    7.  Bucket B files (recency, excluding Bucket A)

6.  **repair\_context truncation**

      * Implement as: `truncated = repair_context[:2000]` in Python (2000 Unicode codepoints).
      * No word-boundary logic, no “smart” trimming.
      * Truncation MUST be logged to `timeline_events` in the same transaction as the update.

7.  **Snapshots**

      * Use exactly the snapshot query defined by the spec, with `json_each` and `json_valid` as per SQLite JSON1, and `ORDER BY file_path ASC`.

-----

## 4\. Database Layer (Phase 1 Deliverables)

### 4.1 Schema & Migrations

Deliverables:

  * `project_builder/database/schema.sql`
  * `project_builder/database/migrations.py`
  * `tests/test_schema.py`

`schema.sql` MUST include:

  * All tables and columns per spec v0.9:
      * `missions`, `mission_tasks`, `artifacts`, `timeline_events`, etc.
  * Critical fields:
      * `missions.repair_budget_usd REAL NOT NULL DEFAULT 0.0`
      * `mission_tasks.tokenizer_model TEXT` (nullable at creation, but MUST be set before execution)
      * `mission_tasks.required_artifact_ids TEXT NULL` (JSON)

**required\_artifact\_ids enforcement**:

Enforcement MUST occur at application level using:

```python
def validate_required_artifact_ids(ids):
    if len(ids) > 3:
        raise ValueError("required_artifact_ids_limit_exceeded")
```

Indexes:

```sql
CREATE INDEX idx_artifacts_snapshot
  ON artifacts(mission_id, file_path, version_number DESC);

CREATE INDEX idx_artifacts_required
  ON artifacts(mission_id, id);

CREATE INDEX idx_timeline_task
  ON timeline_events(task_id, created_at);
```

### 4.2 Snapshot Engine (`snapshot.py`)

Implement:

```python
def snapshot_query(conn, mission_id: str, task_id: str) -> list[tuple[str, bytes]]:
    """Returns a list of (file_path, content_bytes) representing the snapshot
    for mission_id + task_id per spec v0.9."""
    ...
```

Core SQL (illustrative; must match spec v0.9 exactly):

```sql
WITH task AS (
  SELECT started_at, required_artifact_ids
  FROM mission_tasks
  WHERE id = :tid AND mission_id = :mid
),
snapshot_artifacts AS (
  SELECT a.file_path, a.content,
         ROW_NUMBER() OVER (
           PARTITION BY a.file_path
           ORDER BY a.version_number DESC
         ) AS rn
  FROM artifacts a, task t
  WHERE a.mission_id = :mid
    AND a.file_path IS NOT NULL
    AND a.is_deleted = 0
    AND a.created_at <= t.started_at
),
required_artifacts AS (
  SELECT a.file_path, a.content
  FROM artifacts a, task t
  WHERE t.required_artifact_ids IS NOT NULL
    AND json_valid(t.required_artifact_ids) = 1
    AND a.id IN (
      SELECT value FROM json_each(t.required_artifact_ids)
    )
    AND a.mission_id = :mid
    AND a.is_deleted = 0
)
SELECT file_path, content
FROM required_artifacts
UNION
SELECT file_path, content
FROM snapshot_artifacts
WHERE rn = 1
  AND file_path NOT IN (SELECT file_path FROM required_artifacts)
ORDER BY file_path ASC;
```

**Note on Snapshot SQL:** Use of ROW\_NUMBER() CTE MUST match Spec semantics exactly. Ordering is fully deterministic due to enforced `ORDER BY file_path ASC` in final selection.

`tests/test_snapshot.py` MUST include:

  * A case with:
      * multiple versions of same file;
      * tombstones (`is_deleted=1`);
      * `required_artifact_ids` pointing to an older version;
  * And asserts:
      * required artifacts always present;
      * ordering is lexicographic by `file_path`.

### 4.3 Timeline Helpers (`timeline.py`)

Helpers to record events such as:

  * `task_repair_requested`
  * `repair_context_truncated`
  * `required_artifact_ids_limit_exceeded`
  * `task_reclaim_skipped_alive_or_unknown`

Each helper MUST perform DB writes in the same transaction, where relevant.

**Deterministic Timeline Event IDs:**
Timeline event IDs MUST be deterministic.

```python
ID = UUIDv5(namespace=UUID('00000000-0000-0000-0000-000000000001'),
            name=f"{mission_id}:{task_id}:{event_type}:{created_at}:{counter}")
```

Where:

  * `created_at` is truncated to milliseconds.
  * `counter` is a per-task monotonic integer maintained in memory.

-----

## 5\. Orchestrator & FSM (Phase 2 Deliverables)

### 5.1 Budget Transaction (`budget_txn.py`)

Implement:

```python
def try_charge_budget(conn, mission_id: str, task_id: str | None, cost: float, is_repair_attempt: bool) -> bool:
    """Atomically attempts to charge `cost` to the mission budget, and if
    is_repair_attempt, also to the task repair budget. Returns True on success
    (COMMIT), False on failure (ROLLBACK)."""
    ...
```

Normative pattern (matching spec v0.9 / DeepSeek Patch 1):

```python
def try_charge_budget(conn, mission_id, task_id, cost, is_repair_attempt):
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE;")

    # 1. Main mission budget
    cur.execute(
        """
        UPDATE missions
        SET spent_cost_usd = spent_cost_usd + :cost
        WHERE id = :mid
          AND spent_cost_usd + :cost <= max_cost_usd;
        """,
        {"cost": cost, "mid": mission_id},
    )
    cur.execute("SELECT changes()")
    main_ok = cur.fetchone()[0] == 1

    repair_ok = True
    if is_repair_attempt:
        cur.execute(
            """
            UPDATE mission_tasks
            SET repair_budget_spent_usd = repair_budget_spent_usd + :cost
            WHERE id = :tid
              AND repair_budget_spent_usd + :cost <= (
                  SELECT repair_budget_usd FROM missions WHERE id = :mid
              );
            """,
            {"cost": cost, "tid": task_id, "mid": mission_id},
        )
        cur.execute("SELECT changes()")
        repair_ok = cur.fetchone()[0] == 1

    if main_ok and repair_ok:
        conn.commit()
        return True
    else:
        conn.rollback()
        return False
```

**QA:** `tests/test_budget_txn.py` must include:

  * Over-budget mission cost → fails.
  * Over-repair budget on repair attempt → fails.
  * Non-repair tasks do not touch `repair_budget_spent_usd`.
  * No partial charges when transaction fails.

### 5.2 Tokenizer Recording (`context/tokenizer.py`)

**Architectural Change:** To prevent race conditions, we split resolution (pure logic) from recording (DB transaction).

Implement:

```python
def resolve_tokenizer_id(model_config: dict) -> str:
    """Pure function. Returns the stable identifier string for the tokenizer.
    Does NOT access DB."""
    # Logic:
    # If config['provider'] == 'openai' -> return 'tiktoken/cl100k_base'
    # Else -> return config['tokenizer'] or raise ConfigurationError
    ...
```

**Atomicity Requirement (Implementation Rule):**
You MUST NOT implement a standalone "record\_tokenizer" function that commits its own transaction. Instead, the orchestrator MUST execute the recording SQL in the **same transaction** that starts the task.

**Correct Implementation Pattern (in `orchestrator/fsm.py`):**

```python
def start_task_execution(conn, task_id, tokenizer_id, now):
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE;")
    
    # 1. Update status and start time
    # 2. Record tokenizer ID (only if not already set)
    cur.execute("""
       UPDATE mission_tasks
          SET status = 'executing',
              started_at = :now,
              tokenizer_model = COALESCE(tokenizer_model, :tok)
        WHERE id = :tid
    """, {"now": now, "tok": tokenizer_id, "tid": task_id})
    
    conn.commit()
```

### 5.3 FSM (`orchestrator/fsm.py`)

Implement state transitions per spec v0.9 (e.g., `pending → executing → review → approved/repair_retry/failed_terminal`), ensuring:

  * `started_at` set only on `pending/repair_retry → executing`, same transaction as `status='executing'`.
  * `repair_attempt` incremented atomically with transition to `repair_retry`.
  * `repair_context` set and truncated (see §6.1) when QA suggests repair.
  * Mission failure propagation done in same transaction as `failed_terminal` task.

### 5.4 Lock Reclaim (`orchestrator/reclaim.py`)

Implement:

```python
def attempt_reclaim_task(conn, task_id: str, worker_registry) -> bool:
    """Attempts to reclaim a stale-locked task.
    Returns True if reclaim performed, False otherwise."""
    ...
```

**WorkerRegistry API (Required for cross-platform reclaim):**

```python
class WorkerRegistry(ABC):
    @abstractmethod
    def is_alive(self, pid: int) -> bool:
        pass

### POSIX Implementation
class PosixWorkerRegistry(WorkerRegistry):
    def is_alive(self, pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

### Windows Stub
class WindowsWorkerRegistry(WorkerRegistry):
    def is_alive(self, pid):
        # Use psutil or Windows API. If unavailable → return unknown.
        return False  # Unknown → do NOT reclaim.
```

Rules:

  * Load `locked_by` and `locked_at` from DB.
  * Determine liveness:
      * If `locked_by` cannot be parsed OR registry returns unknown:
          * Log `task_reclaim_skipped_alive_or_unknown`.
          * Do NOT reclaim.
  * If worker is alive → do NOT reclaim.
  * If dead and lock expired:
      * Clear `locked_by` and `locked_at`.
      * Do **NOT** change `started_at` or `repair_attempt`.
      * Delete workspace via `sandbox/workspace.py`.
      * Log `task_reclaimed`.

### 5.5 Backpressure Control (Spec §10.5)

#### Purpose

Prevent unbounded task creation or runaway parallelism by pausing mission progression when pending or active messages exceed defined thresholds.

#### Configuration & Definitions

Replace hardcoded constants with dynamic calculation logic.

```python
# In project_builder/config/settings.py
BASE_PENDING_LIMIT = 50
MAX_PENDING_PER_TASK = 10

def compute_backpressure_thresholds(task_count: int) -> tuple[int, int]:
    """Returns (max_pending, resume_threshold) based on Spec §10.5"""
    max_pending = max(BASE_PENDING_LIMIT, task_count * MAX_PENDING_PER_TASK)
    resume_threshold = int(max_pending * 0.6)
    return max_pending, resume_threshold
```

#### Orchestrator Responsibilities

Implement `check_and_apply_backpressure()` using these dynamic limits.

  * **Pending Calculation:** `tasks with status IN ('pending','repair_retry') + pending messages`.
  * **Pause:** If pending \> max\_pending:
    1.  Transition mission to `paused_error`.
    2.  Reject new tasks.
  * **Resume:** If pending \< resume\_threshold:
    1.  Transition mission back to `executing` (or previous state).
    2.  Maintain `repair_context` and `repair_attempt`.
    3.  Do not reset `started_at`.

### 5.6 Planner Validation (Spec §7.4)

You MUST implement the **80% Budget Fraction** enforcement logic.

**Implementation:**
Add this validation function to `project_builder/agents/planner.py`:

```python
PLANNER_BUDGET_FRACTION = 0.8

def validate_plan_budget(conn, mission_id: str, estimated_cost_usd: float) -> None:
    """Raises ValueError if planner estimate exceeds 80% of mission budget."""
    cur = conn.cursor()
    cur.execute("SELECT max_cost_usd FROM missions WHERE id = ?", (mission_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("mission_not_found")
    
    max_cost = row[0]
    if estimated_cost_usd > max_cost * PLANNER_BUDGET_FRACTION:
        raise ValueError("planner_budget_fraction_exceeded")
```

**Usage:**
This function MUST be called in the orchestrator before accepting a PLAN message and writing tasks to `mission_tasks`.

-----

## 6\. Context Injection & Token Accounting (Phase 2/3 Shared)

### 6.1 repair\_context Truncation (`context/truncation.py`)

Implement:

```python
MAX_REPAIR_CONTEXT_CHARS = 2000

def truncate_repair_context(text: str) -> str:
    return text[:MAX_REPAIR_CONTEXT_CHARS]
```

**Atomic Repair Context Update:**
MODIFY to use normative wrapper:

```python
def update_repair_context_atomic(conn, task_id, new_context):
    truncated = new_context[:2000]
    cur = conn.cursor()
    cur.execute("BEGIN IMMEDIATE;")
    cur.execute("""
       UPDATE mission_tasks
          SET repair_context = :ctx
        WHERE id = :tid""",
        {"ctx": truncated, "tid": task_id}
    )
    cur.execute("""
       INSERT INTO timeline_events
          (task_id, event_type, metadata)
       VALUES (:tid, 'repair_context_truncated', json_object('length', length(:ctx)))
    """, {"tid": task_id, "ctx": truncated})
    conn.commit()
```

Usage:

  * Called **before** persisting `repair_context` into `mission_tasks`.
  * If truncation occurs, record `timeline_events` with `event_type='repair_context_truncated'` in the same DB transaction.

`tests/test_repair_context.py`:

  * Insert a long suggestion (e.g., 3500 chars).
  * Apply `update_repair_context_atomic`.
  * Assert stored length = 2000, event logged.

### 6.2 Context Builder (`context/injection.py`)

Implement:

```python
def build_context_components(task, snapshot_files, repair_context, qa_feedback, file_tree_str, tokenizer) -> list[str]:
    """Returns ordered list of text components that will be concatenated or
    sent separately to the LLM. Enforces bucket priority and deterministic
    ordering."""
    ...
```

Buckets:

  * **Bucket A (priority):**
      * Files listed in `mission_tasks.context_files` (if any).
      * Files referenced by `required_artifact_ids`.
  * **Bucket B (recency):**
      * All other snapshot files, sorted by `created_at DESC` then `file_path ASC`, **excluding** Bucket A.

Token budget logic:

1.  Start with system + mission + task + repair\_context + file\_tree + QA feedback.
2.  Then include Bucket A files in deterministic order.
3.  Then include Bucket B files until hitting budget.
4.  When truncating file contents, insert the spec’s truncation marker `"[...TRUNCATED BY COO...]"`.

`tests/test_tokenizer_replay.py`:

  * Use fixed content and a test tokenizer (count chars).
  * Ensure same tokens chosen across multiple runs.

-----

## 7\. Sandbox & Security (Phase 3 Deliverables)

### 7.1 Workspace Materialization (`sandbox/workspace.py`)

Implement:

```python
from pathlib import Path

class SecurityViolation(Exception):
    pass

def materialize_workspace(root: Path, files: list[tuple[str, bytes]]) -> None:
    """Writes files into the workspace under `root`, enforcing path
    normalization and security."""
    ...
```

Path validation:

  * For each `file_path`:
      * Reject if contains `\` or `..` or starts with `/`.

      * Use canonicalization:

        ```python
        resolved = (root / file_path).resolve()
        if not str(resolved).startswith(str(root.resolve())):
            raise SecurityViolation("invalid_artifact_path")
        ```

### 7.2 Manifest Ingestion (`sandbox/manifest.py`)

**Early Path Validation:**
All path validation MUST occur at manifest parse time, before any artifact is persisted. Reject immediately if path:

  * Contains `\`
  * Contains `..`
  * Starts with `/`
  * Fails regex `^[A-Za-z0-9._ -]+(/[A-Za-z0-9._ -]+)*$` (Allow spaces, deny other special chars)

Manifest rules:

  * Only accept manifest at: `/workspace/.coo-manifest.json`.
  * For each entry:
      * Validate `path` with regex above.
      * Validate `checksum` format: `^sha256:[0-9a-f]{64}$`.

Checksum & line endings:

  * For text files:
      * Normalize to UTF-8.
      * Replace CRLF (`\r\n`) with LF (`\n`) before hashing.
      * Compute SHA256 and prefix with `sha256:` in DB.
  * If checksum mismatch:
      * Fail task with `sandbox_checksum_mismatch`.
      * Do not create artifact rows.

### 7.3 Symlink Ban (`sandbox/security.py`)

After sandbox run:

```python
for p in root.rglob("*"):
    if p.is_symlink():
        raise SecurityViolation("sandbox_invalid_symlink")
```

  * On detection:
      * Mark task `failed_terminal` with reason `sandbox_invalid_symlink`.
      * Log event in `timeline_events`.

### 7.4 Sandbox Runner (`sandbox/runner.py`)

  * Run container with:
      * `--network=none`
      * `--cap-drop=ALL`
      * `--security-opt=no-new-privileges`
      * Resource limits (configurable):
          * `--memory=1g`
          * `--cpus=1`
  * No `--privileged` flag allowed.
  * The **Runtime Contract** explicitly forbids any manifest coming from stdout; ingestion MUST be file-only.

-----

## 8\. Testing & QA Gates

The following tests MUST exist and pass:

### 8.1 Schema & JSON1

  * `test_schema.py`:
      * Ensure `missions`, `mission_tasks`, `artifacts`, `timeline_events` exist with all required columns.
      * Verify JSON1 availability with a simple `SELECT json_valid('["a"]');`.

### 8.2 Snapshot & required\_artifact\_ids

  * `test_snapshot.py`:
      * Version selection correctness.
      * `required_artifact_ids` always included.
      * Enforcement of length ≤ 3 in planner validation (and optionally DB CHECK).
      * Performance test on large artifact sets (e.g., 10k rows) using `EXPLAIN QUERY PLAN` to confirm index usage.

### 8.3 Budget Transaction

  * `test_budget_txn.py`:
      * Over-spend mission → fails.
      * Over-repair budget on repair attempts → fails.
      * Non-repair tasks do not touch `repair_budget_spent_usd`.
      * No partial charges when transaction rolls back.
      * **New:** `test_budget_concurrent_access`: Two concurrent BEGIN IMMEDIATE attempts; ensure one serializes, other retries/blocks.

### 8.4 FSM & Repair

  * `test_fsm.py`:
      * All valid transitions.
      * `started_at` behavior (set once per attempt).
      * Mission failure propagation.
      * **New:** `test_backpressure_preserves_repair_state`: Enter `paused_error` with repair\_attempt=2, repair\_context='X'; Resume → values preserved.
  * `test_repair_context.py`:
      * Truncation to 2000 code points.
      * `repair_context_truncated` event creation.
      * **New:** `test_repair_context_unicode_truncation`: Insert multibyte Unicode \> 2000 codepoints; stored length == 2000 codepoints.

### 8.5 Tokenizer & Replay

  * `test_tokenizer_replay.py`:
      * Same tokenizer recorded and used on replay (OpenAI + non-OpenAI).
      * Same context composition and token count for the same input snapshot.

### 8.6 required\_artifact\_ids Limit

  * `test_required_artifact_ids.py`:
      * Plan with \>3 IDs → rejected.
      * CEO QUESTION emitted.
      * `required_artifact_ids_limit_exceeded` recorded in timeline.
      * **New:** `test_required_artifact_ids_task_update`: Attempt to UPDATE task with \>3 IDs → reject.

### 8.7 Sandbox Security

  * `test_sandbox_security.py`:
      * Path traversal attempts rejected.
      * Symlink creation causes task failure.
      * Invalid checksum causes `sandbox_checksum_mismatch`.
      * Invalid manifest paths or backslashes cause `invalid_artifact_path`.

### 8.8 End-to-End Determinism

  * `test_end_to_end.py`:
      * Run a mission with 2–3 tasks, including a repair.
      * Store snapshots and artifacts.
      * Replay mission and assert identical:
          * `artifacts` table (file\_path, checksum)
          * `timeline_events` ordering and key fields.

### 8.9 Planner Validation

  * `test_planner_validation.py`:
      * **New:** `test_planner_budget_exceeded`: Create mission max\_cost=10, Plan estimate=9. → ValueError("planner\_budget\_fraction\_exceeded").
      * **New:** `test_planner_budget_ok`: Create mission max\_cost=10, Plan estimate=8. → Success.

-----

## 9\. Deployment & Ops Playbook

### 9.1 Docker Build

  * `docker/Dockerfile`:
      * Install Python + dependencies.
      * Ensure SQLite JSON1.
  * Verify JSON1 at container start with a small script (e.g., `SELECT json_valid('["a"]');`).

### 9.2 Migrations

  * `python -m project_builder.database.migrations upgrade`
  * Migrations MUST be idempotent and safe to run multiple times.

### 9.3 Handling Stale Locks

  * CLI command (shape):
    ```bash
    coo debug mission <id> --show-locks
    ```
  * Operator can:
      * Inspect `locked_by`, `locked_at`.
      * Force reclaim only when allowed per reclaim policy.
      * **Force Unlock:** If a lock is held by a "garbage" or "unknown" ID for a significant period (e.g. \> 24 hours), the operator may use `--force` to manually break the lock. This is an operational escape hatch and should be used with caution.

### 9.4 Config Schema

  * `project_builder/config/settings.py` must define:
      * `MAX_REPAIRS_PER_TASK`
      * `TASK_LOCK_TIMEOUT_SECONDS`
      * `DEFAULT_SANDBOX_MEMORY_MB`
      * `DEFAULT_SANDBOX_CPUS`
      * `PLANNER_BUDGET_FRACTION` (0.8)

-----

## 10\. Phase Plan & Deliverables (Recap)

### Phase 1 — DB Layer

Deliver:

  * `schema.sql`, `migrations.py`, `snapshot.py`, `timeline.py`
  * Tests: schema, snapshot, required\_artifact\_ids

### Phase 2 — Orchestrator & Context

Deliver:

  * `fsm.py`, `budget_txn.py`, `reclaim.py`, `routing.py`, `missions.py`
  * `tokenizer.py`, `injection.py`, `truncation.py`
  * `agents/planner.py` (validation logic)
  * Tests: budget\_txn, fsm, repair\_context, tokenizer\_replay, planner\_validation

### Phase 3 — Sandbox & Security

Deliver:

  * `workspace.py`, `manifest.py`, `security.py`, `runner.py`
  * Tests: sandbox\_security, checksum, path validation

### Phase 4 — End-to-End Missions

Deliver:

  * `cli/main.py` (replay, debug)
  * End-to-end deterministic tests.

-----

## 11\. Code Review Gates

The following changes MUST be reviewed by a senior or council-proxy before merge:

  * Any modification to:
      * `snapshot.py`
      * `budget_txn.py`
      * `tokenizer.py`
      * `reclaim.py`
      * `security.py` (path normalization, symlink logic)
  * Any change touching:
      * `BEGIN IMMEDIATE` logic
      * Tokenizer recording semantics
      * required\_artifact\_ids logic
      * repair\_context truncation logic

-----

## 12\. Version Control & Release Management

### 12.1 Git Branching Model

Use a simple, strict branching model:

  * `main`
      * Always in a **releasable** state.
      * Only receives merged PRs that pass all tests.
  * `develop` (optional)
      * Staging branch for feature integration before merging to `main`.
  * `feature/*` branches
      * E.g. `feature/snapshot-engine`, `feature/budget-txn`, `feature/sandbox-security`.
      * All implementation work for this project is done on feature branches.
  * `chore/*` branches
      * For non-functional changes: documentation, refactors, tooling.

Each feature branch MUST:

1.  Be associated with a clear ticket / issue describing the change.
2.  Include or update tests relevant to the change.
3.  Update `docs/CHANGELOG.md` when the change impacts behavior.

### 12.2 Tagging & Releases

  * Tag the spec commit as:
      * `spec/project-builder-v0.9`
  * Tag the implementation commit (first stable version matching this packet) as:
      * `impl/project-builder-v0.9.7`

Subsequent compatible changes:

  * Bug fixes without spec change:
      * `impl/project-builder-v0.9.8`, etc.
  * If the spec itself changes (e.g. v0.10), create:
      * New spec tag: `spec/project-builder-v0.10`
      * New implementation packet: `Implementation_Packet_v0_10_0.md`
      * New impl tag: `impl/project-builder-v0.10.0`

### 12.3 Pull Request Requirements

Every PR MUST:

1.  Reference:
      * Spec version: `Spec v0.9`
      * Implementation packet version: `Packet v0.9.7`
2.  Include:
      * Summary of changes.
      * List of touched modules.
      * Tests added/updated.
3.  Pass CI:
      * All tests in `tests/` must pass.
4.  Get at least:
      * One reviewer with familiarity with this packet.
      * For code touching critical paths (snapshot, budget, tokenizer, reclaim, security), at least one **senior** review.

Recommended PR template:

```markdown
### Summary
- What does this change?

### Spec Alignment
- Spec version: v0.9
- Implementation Packet: v0.9.7

### Modules Touched
- project_builder/orchestrator/budget_txn.py
- tests/test_budget_txn.py

### Tests
- [x] pytest tests/test_budget_txn.py
- [x] pytest tests/test_end_to_end.py

### Risk
- [ ] Low  [x] Medium  [ ] High

### Notes
- Any deviations or open questions vs spec?
```

### 12.4 CHANGELOG Discipline

`docs/CHANGELOG.md` MUST record:

  * Date
  * Author
  * Summary
  * Whether behavior is strictly internal (no external API change) or user-visible
  * Spec/Packet versions affected

Example entry:

```markdown
## [0.9.7] - 2025-11-22
### Added
- Implemented budget_txn.py using BEGIN IMMEDIATE pattern.
- Added tokenizer.py for tokenizer_model selection & recording.
- Introduced sandbox/security.py with symlink detection.
- Added Backpressure Control logic with dynamic limits (Spec §10.5).
- Added POSIX/Windows WorkerRegistry for lock reclaim.
- Added Planner Budget Fraction enforcement (80% rule).

### Fixed
- Enforced required_artifact_ids <= 3 at planner validation level.
- Verified JSON1 availability on startup.
- Relaxed manifest regex to allow spaces in filenames.
- Hardened Tokenizer atomicity to require update within the FSM transaction.

### Notes
- Aligned with GPTCOO v1.1 Project Builder Spec v0.9 and Implementation Packet v0.9.7.
```

### 12.5 Release Checklist

Before tagging `impl/project-builder-v0.9.7`:

1.  All tests in `tests/` pass.
2.  End-to-end determinism test (`test_end_to_end.py`) passes.
3.  Replay test confirmed manually on one reference mission.
4.  `CHANGELOG.md` updated.
5.  Implementation Packet path `docs/Implementation_Packet_v0_9_7.md` committed.
6.  Reviewed and approved by:
      * One engineer focused on infra/DB.
      * One engineer focused on sandbox/security.
      * Operator/CEO (you) or delegate.

After this checklist, create tag:

```bash
git tag impl/project-builder-v0.9.7
git push origin impl/project-builder-v0.9.7
```

-----

This packet, together with the v0.9 spec, is sufficient for a junior engineer to implement the GPTCOO v1.1 Project Builder correctly, deterministically, securely, and under disciplined version control.