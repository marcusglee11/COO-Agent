# **COO Multi-Agent System Specification v0.6-FINAL**
**"The Deterministic Agent Runtime"**

---

## **Document Control**
- **Version**: 0.6-FINAL
- **Date**: 2025-11-19
- **Status**: Pre-Implementation (Ready for Build)
- **Maintainer**: Kimi (Primary Engineer)
- **Review Process**: 
  - ChatGPT: Architecture & Orchestration
  - Gemini: Security & Sandbox
  - GLM-4.6: Boilerplate, Fixtures, Config Templates
- **Change Log**: Integrated all amendments from Claude/Gemini/GLM review cycle; v0.6 consolidates v0.5-FINAL + amendment pack + critical path fixes from Claude review

---

## **1. Executive Summary**

Build a **self-directed multi-agent system** where:
- **CEO (you)** provides natural-language missions via chat
- **COOAgent** plans and decomposes work
- **EngineerAgent** writes code and requests execution
- **QAAgent** reviews and gates execution
- All communication via **SQLite message bus** (no OpenAI runtime dependency)
- **Hard budget enforcement** (deterministic, no LLM self-estimation)
- **Network-isolated Docker sandbox** (no exceptions)
- **Multi-mission from day one** (bounded concurrency)
- **Crash recovery** with heartbeat-based message reclaim
- **Streaming UX**: CEO sees live progress via `STREAM` messages

**Shippable in ~6 weeks (solo dev).**

### **Key Design Decisions (v1.0)**

* Polling-based orchestrator (not event-driven) for simplicity
* Sync HTTP clients + ThreadPoolExecutor (async HTTP deferred to v1.1)
* Hard per-agent token limits (no LLM self-governance)
* Fat Docker image with pre-installed safe packages (no runtime `pip install`)
* SQLite (WAL) as the only message bus and global state-of-truth

---

## **2. Goals & Non-Goals**

### **2.1 Goals (v1.0)**
1. Single orchestrator binary (`coo`) that runs multiple missions concurrently
2. COO → Engineer → QA message flow with approval gates
3. Code execution in **network-none, non-root Docker containers**
4. **Hard cap budget enforcement** with transaction rollback on exceed
5. **Streaming UX**: CEO sees live progress via `STREAM` messages (CLI polling)
6. **Crash recovery**: Messages reclaimed after agent timeout
7. **Backpressure**: Hard pause if mission generates >50 pending messages (configurable)
8. **Observability**: Structured JSON logs + DB timeline events

### **2.2 Non-Goals (v1.0 Explicit)**
- **No task DAG or dependency graph** (linear task lists only)
- **No conversation summary tables** (context window management only)
- **No alerting subsystem** (CLI status only)
- **No circuit breaker infrastructure** (simple pause logic)
- **No config schema migrations** (YAML files only)
- **No multi-worker orchestrators** (single process only)
- **No multi-storage artifact system** (inline TEXT only)
- **No async HTTP clients** (ThreadPoolExecutor for blocking calls)
- **No web UI** (CLI only for v1.0)
- **No user authentication / multi-user model** (single local operator)
- **No horizontal scaling** (single orchestrator process, single machine; all "multi-instance" is v2+)

**Streaming UX**: CLI polls `messages` table for kind=STREAM every 1s, displays live to CEO. Not WebSocket; simple polling.

**Backpressure**: Configurable per mission; default `max_pending_messages: 50` in orchestrator config.

---

## **3. High-Level Architecture**

```
CEO (CLI Chat)
    ↑↓
┌─────────────────────────────────────────┐
│  Orchestrator (Single Python Process)   │
│  - Asyncio main loop                    │
│  - ThreadPoolExecutor for LLM calls     │
│  - BudgetGuard (pre/post call)          │
│  - MessageStore (SQLite with WAL)       │
│  - Sandbox handler (direct SANDBOX_EXECUTE)│
└─────────────────────────────────────────┘
    ↑↓ (message bus)
┌──────────┬──────────┬──────────┐
│ COOAgent │ Engineer │ QAAgent  │
│ (Planner)│ (Coder)  │ (Reviewer)│
└──────────┴──────────┴──────────┘
    ↓ (SANDBOX_EXECUTE)
┌─────────────────────────────────────────┐
│  Docker Sandbox (Ephemeral, No Network)│
│  - Bind mount temp workspace           │
│  - Non-root user (1000:1000)           │
│  - Resource limits (512m RAM, 50% CPU) │
│  - --security-opt=no-new-privileges    │
│  - Readonly rootfs (v1.1)              │
└─────────────────────────────────────────┘
    ↓ (artifacts)
┌─────────────────────────────────────────┐
│  SQLite DB (coo.db, WAL mode)          │
│  - messages (durable queue)            │
│  - missions (FSM state)                │
│  - artifacts (inline content)          │
│  - sandbox_runs (idempotency)          │
│  - budget tracking                     │
└─────────────────────────────────────────┘
```

**CLI Commands (v1.0)**

* `coo orchestrator` – start the long-running orchestrator daemon
* `coo chat` – CEO-facing interactive chat that writes messages to DB and reads results/STREAMs
* `coo status` – list missions and budgets (`--all`, `--json`)
* `coo mission <id> [--follow]` – per-mission view, optionally follow progress (`--logs`, `--timeline`)
* `coo logs --mission <id> [--tail N]` – show recent timeline/log events
* `coo dlq ...` – dead-letter queue tools (`list`, `show <id>`, `replay <id>`)
* `coo metrics --daily` – daily/monthly spend

*Note: The CLI is just a DB client; there is no network API between CLI and orchestrator.*

---

## **4. Detailed Specification**

### **4.1 Persistence Layer (SQLite)**

**File**: `~/.local/share/coo/coo.db` (WAL mode)

**Connection Settings:**
```python
# In message_store.py
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;        # Wait 5s on lock conflict
```

**Core Tables:**

```sql
-- Missions table
CREATE TABLE missions (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,               -- created, planning, executing, reviewing, paused_*, completed, failed
    previous_status TEXT,               -- for resuming from paused_*
    description TEXT NOT NULL,

    -- Explicit config fields (pulled from JSON for queryability)
    max_cost_usd REAL NOT NULL,
    max_loops INTEGER NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    budget_increase_requests INTEGER NOT NULL DEFAULT 0,

    config_json TEXT,                   -- remaining mission-specific config

    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    completed_at DATETIME,
    failed_at DATETIME,
    failure_reason TEXT,
    spent_cost_usd REAL NOT NULL DEFAULT 0,
    loop_count INTEGER NOT NULL DEFAULT 0,
    message_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_missions_status ON missions(status);

-- Messages = durable queue
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    from_agent TEXT NOT NULL,
    to_agent TEXT NOT NULL,
    kind TEXT NOT NULL,                 -- TASK, RESULT, STREAM, ERROR, APPROVAL, SANDBOX_EXECUTE, CONTROL, QUESTION, SYSTEM
    status TEXT NOT NULL,               -- pending, processing, delivered, failed, expired
    body_json TEXT NOT NULL,            -- JSON string
    schema_version INTEGER NOT NULL DEFAULT 1,
    
    priority INTEGER NOT NULL DEFAULT 5,
    correlation_id TEXT,
    conversation_id TEXT,
    in_reply_to TEXT,
    
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    timeout_at DATETIME,
    locked_at DATETIME,                 -- Last heartbeat timestamp
    locked_by TEXT,                     -- Format: "{hostname}_{pid}", e.g. "laptop_12345"
    
    error_type TEXT,
    error_detail TEXT,
    
    created_at DATETIME NOT NULL,
    processed_at DATETIME
);
CREATE INDEX idx_messages_pending ON messages(to_agent, status, mission_id) WHERE status = 'pending';
CREATE INDEX idx_messages_mission ON messages(mission_id, created_at);
CREATE INDEX idx_messages_stale 
  ON messages(locked_at, status)
  WHERE status = 'processing' AND locked_at IS NOT NULL;

-- Artifacts (v1: inline content only)
CREATE TABLE artifacts (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    type TEXT NOT NULL,                 -- code, text, json, log, binary
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content TEXT NOT NULL,              -- inline TEXT (files < 1MB)
    storage_type TEXT NOT NULL DEFAULT 'inline',
    path TEXT,                          -- future: filesystem path for large files
    checksum TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    created_by TEXT NOT NULL
);
CREATE INDEX idx_artifacts_mission ON artifacts(mission_id, created_at);

-- Agents registry
CREATE TABLE agents (
    name TEXT PRIMARY KEY,
    model_name TEXT NOT NULL,
    status TEXT NOT NULL,               -- active, disabled
    last_active DATETIME,
    error_streak INTEGER NOT NULL DEFAULT 0,
    total_invocations INTEGER NOT NULL DEFAULT 0,
    total_cost_usd REAL NOT NULL DEFAULT 0,
    avg_duration_ms REAL,
    success_rate REAL,
    capabilities_json TEXT,
    config_json TEXT                    -- {max_tokens_per_call, temperature}
);

-- Dead-letter queue
CREATE TABLE dead_letters (
    id TEXT PRIMARY KEY,
    original_message_id TEXT NOT NULL REFERENCES messages(id),
    mission_id TEXT NOT NULL REFERENCES missions(id),
    failed_at DATETIME NOT NULL,
    error_type TEXT NOT NULL,
    error_detail TEXT,
    retry_count INTEGER NOT NULL,
    payload_snapshot TEXT NOT NULL
);
CREATE INDEX idx_dead_letters_mission ON dead_letters(mission_id, failed_at);

-- Timeline events (append-only)
CREATE TABLE timeline_events (
    id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    event_type TEXT NOT NULL,           -- agent_invoked, state_transition, cost_update, sandbox_run, error
    event_json TEXT NOT NULL,
    created_at DATETIME NOT NULL
);
CREATE INDEX idx_timeline_mission ON timeline_events(mission_id, created_at);

-- Budget tracking (global)
CREATE TABLE budgets_global (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    daily_budget_usd REAL NOT NULL,
    daily_spent_usd REAL NOT NULL DEFAULT 0,
    monthly_budget_usd REAL NOT NULL,
    monthly_spent_usd REAL NOT NULL DEFAULT 0,
    updated_at DATETIME NOT NULL
);
-- Note: A daily/monthly reset task (or orchestrator startup check) will zero daily_spent_usd/monthly_spent_usd when date(updated_at) is stale.

-- Sandbox runs (idempotency + crash recovery)
CREATE TABLE sandbox_runs (
    dedupe_id TEXT PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(id),
    artifact_id TEXT NOT NULL REFERENCES artifacts(id),

    status TEXT NOT NULL,              -- running, completed, failed
    result_artifact_id TEXT,
    exit_code INTEGER,

    started_at DATETIME NOT NULL,
    completed_at DATETIME
);
CREATE UNIQUE INDEX idx_sandbox_dedupe ON sandbox_runs(dedupe_id);
CREATE INDEX idx_sandbox_runs_mission ON sandbox_runs(mission_id, started_at);
```

---

### **4.2 Messaging Protocol**

**Canonical Message Structure:**
```json
{
  "id": "msg_001",
  "schema_version": 1,
  "from_agent": "COO",
  "to_agent": "Engineer",
  "mission_id": "m_42",
  "conversation_id": "conv_001",
  "in_reply_to": null,
  "priority": 5,
  "kind": "TASK",
  "status": "pending",
  "retry_count": 0,
  "max_retries": 3,
  "timeout_at": "2025-01-20T15:00:00Z",
  "created_at": "2025-01-20T14:30:00Z",
  "body_json": {
    "action": "implement_feature",
    "summary": "Create Fibonacci function",
    "details": "Implement fibonacci(n) with docstring",
    "context_refs": ["artifact_codebase_main"],
    "required_capabilities": ["python"],
    "checksum": "sha256:..."
  }
}
```

**Complete Message Kinds (v1 Protocol):**
- `TASK` - Request to perform work
- `RESULT` - Response with output/artifact
- `STREAM` - Incremental progress update (live UX)
- `ERROR` - Failure report with `error_type`
- `APPROVAL` - CEO/QA approval/rejection gate
- `SANDBOX_EXECUTE` - System command to execute code (idempotent)
- `CONTROL` - System-level instructions (pause, resume, budget increase)
- `QUESTION` - Clarification request
- `SYSTEM` - Internal orchestration messages

**Message Kind Permissions (v1.0)**

| Message Kind | Allowed From → To |
|--------------|-------------------|
| `TASK` | COO → Engineer/QA |
| `RESULT` | Engineer/QA/System → COO |
| `STREAM` | any agent → CEO (via CLI polling) |
| `ERROR` | any agent/system → any |
| `APPROVAL` | CEO → COO |
| `QUESTION` | COO → CEO |
| `SANDBOX_EXECUTE` | Engineer → System (orchestrator only) |
| `CONTROL` | CEO → Orchestrator (pause/resume/cancel) |
| `SYSTEM` | Orchestrator → any agent |

**Top-level fields clarification:**
- `correlation_id` is a top-level field only (not duplicated in `meta`)
- `checksum` is a top-level field only (moved from `meta` to root in schema)

---

### **4.3 Agent Interface (Async Generator)**

**File**: `agent.py`

```python
from abc import ABC, abstractmethod
from typing import Generator, Dict, Any, List
from dataclasses import dataclass

@dataclass
class Emission:
    type: str  # "message" | "side_effect" | "sandbox_execute"
    data: Dict[str, Any]

class Agent(ABC):
    name: str
    timeout_seconds: int = 300

    @abstractmethod
    def process_stream(
        self, mission: Dict[str, Any], messages: List[Dict[str, Any]]
    ) -> Generator[Emission, None, None]:
        """
        Yielding generator that emits emissions as work progresses:
        - Emission(type="message", data={...}) → STREAM/RESULT/etc
        - Emission(type="side_effect", data={cost_delta_usd, state_transition, ...})
        - Emission(type="sandbox_execute", data={artifact_id, entrypoint, timeout, dedupe_id})
        
        Must be deterministic/idempotent for same inputs.
        The orchestrator (not the agent) is responsible for updating `locked_at` 
        periodically (e.g. every 30s) while processing a batch with an agent's generator.
        """
        pass

    def process(self, mission, messages):
        """Legacy one-shot (default impl). Override for streaming agents."""
        raise NotImplementedError

```

**Context Window Management (v1):**
- **Always included**: Mission description, config
- **Last K messages**: K = 5 (hardcoded in v1)
- **No summarization**: Older messages dropped silently
- **No vector DB**: All context in prompt text
- **System Prompt Rule**: For every agent and every LLM call, ModelClient must prepend:
  1. Agent's System Prompt as the first system message (stored in `prompts/<agent>/...`)
  2. Mission descriptor/system context as the second system message (or merged)
  3. Then the last **K = 5** messages for that conversation (sliding window)
  4. Older messages beyond the last 5 are dropped (no summarization in v1.0)

**Known limitation**: Summarization/vector search are deferred to v1.1+.

**Agent Capabilities (lightweight registry):**
```python
AGENT_CAPABILITIES = {
    "COO": ["planning", "json_output"],
    "Engineer": ["python", "code_generation"],
    "QA": ["code_review", "testing"]
}
```
This is purely descriptive for now, to align with `required_capabilities` in message bodies.

---

### **4.4 Mission Lifecycle (FSM)**

**States:**
- `created` → `planning` → `executing` → `reviewing` → `completed`
- `paused_budget`, `paused_approval`, `paused_error`, `paused_manual`, `failed`

**Transitions:**
| From | Event | To | Guard |
|------|-------|----|-------|
| `created` | `plan_ready` | `planning` | COO finished plan |
| `planning` | `budget_exhausted` | `paused_budget` | Pre-check failed |
| `executing` | `budget_exceeded` | `failed` | Post-call rollback |
| `executing` | `approval_requested` | `paused_approval` | Budget increase needed |
| `executing` | `backpressure_exceeded` | `paused_error` | >50 pending messages |
| `any` | `manual_pause` | `paused_manual` | CEO CONTROL message |
| `any` | `_fatal_error` | `failed` | Unrecoverable error |
| `any` | `paused_timeout` | `failed` | 24h in paused_* state |

**Implementation**: `StateManager.transition(mission_id, event)` validates, updates DB, writes timeline event, logs.

**Paused Timeout**: Missions in any `paused_*` state for more than 24 hours without CEO intervention automatically transition to `failed` with `failure_reason='paused_timeout'`.

**Backpressure Hysteresis**: If a mission is in `paused_error` due to backpressure, and its pending messages drop below a `resume_threshold` (default 30), the orchestrator may automatically transition the mission back to `executing`. This avoids flapping. The `resume_threshold` is configurable in orchestrator config.

---

### **4.5 Budget & Cost Governance**

**Hard Cap Rules (Deterministic):**

1. **Per-agent token limits** (enforced in `ModelClient`, no LLM override):
   ```yaml
   agents:
     COO: { max_tokens_per_call: 6000 }
     Engineer: { max_tokens_per_call: 8000 }
     QA: { max_tokens_per_call: 4000 }
   ```

2. **Pre-call check** (BudgetGuard with transaction):
   ```python
   # Transactional budget reservation pattern:
   # BEGIN IMMEDIATE;
   # SELECT spent_cost_usd, max_cost_usd, safety_margin 
   # FROM missions WHERE id = ? FOR UPDATE;
   # Check: spent + worst_case <= max_cost_usd * safety_margin
   # If OK, UPDATE missions SET spent_cost_usd = spent_cost_usd + worst_case
   # COMMIT
   
   worst_case = agent.max_tokens_per_call * pricing[model]["output_per_1k"] / 1000
   if spent + worst_case > max_cost * 0.95:
       transition(mission_id, "paused_budget")
   ```

3. **Post-call enforcement** (BudgetGuard):
   ```python
   def commit(self, actual_cost: float, actual_tokens: int):
       if actual_tokens > self.token_limit:
           raise SecurityViolation()
       self.spent += actual_cost
       if self.spent > self.max_cost:
           raise BudgetExceededError()  # triggers rollback
   ```

4. **Rollback**: Each LLM call wrapped in DB transaction. On `BudgetExceededError`:
   - Delete artifacts from this transaction
   - Revert `missions.spent_cost_usd`
   - Transition to `failed`
   - Emit timeline event

5. **Budget increase limit**: Max 3 requests per mission (`budget_increase_requests` field), then `paused_error`.

---

### **4.6 Sandbox Execution (Direct SANDBOX_EXECUTE)**

**Message Kind**: `SANDBOX_EXECUTE` (system-handled, not LLM-routed)

**Body Schema:**
```json
{
  "artifact_id": "art_123",
  "entrypoint": "python main.py",
  "timeout": 300,
  "dedupe_id": "msg_001",  # Use message.id for idempotency
  "reply_to": "COO"         # Who gets RESULT
}
```

**Orchestrator Flow:**
1. Check `dedupe_id` in `sandbox_runs` table
2. Materialize artifact to fresh temporary workspace: `tempfile.TemporaryDirectory(prefix=f"coo-{mission_id}")`
3. **Docker run**:
   ```bash
   docker run --rm \
     --network none \
     --user 1000:1000 \
     --security-opt=no-new-privileges \
     -m 512m --cpus 0.5 \
     -v <temp_workspace>:/workspace \
     coo-sandbox:latest \
     bash -c "cd /workspace && {entrypoint}"
   ```
4. Capture stdout/stderr, exit code
5. Store result as artifact (`type: log`)
6. Insert `sandbox_runs` row with `dedupe_id`
7. Emit RESULT message to QA/COO
8. **Cleanup**: Delete temporary workspace directory after run (success or failure)

**Security (Non-Negotiable):**
- `--network none` (no internet, ever)
- `--user 1000:1000` (non-root)
- `--security-opt=no-new-privileges` (no privilege escalation)
- Resource limits: 512m RAM, 50% CPU
- **Fat image**: `coo-sandbox:latest` pre-baked with Python 3.11 and curated safe libraries (pytest, requests, numpy, pandas, pydantic, black, flake8, etc.). **No runtime `pip install` allowed.** EngineerAgent is prompted not to invoke `pip install`. Any attempt will fail in-container.
- **Docker failure**: If daemon unreachable → mission `failed`, no unsandboxed fallback.

**Crash Recovery for sandbox_runs:**
On orchestrator startup or periodic checks, any `sandbox_runs` with `status='running'` and `started_at < now - 10 minutes` are considered "abandoned". They are marked `status='failed'`, and corresponding requests may be retried or reported as `ERROR` messages per mission policy.

**Docker Failure Classification:**
- If error contains "permission denied" → `docker_permission_error` + hint: "Run: sudo usermod -aG docker $USER"
- If error contains "not found" → `docker_not_installed`
- Otherwise → `docker_api_error`

---

### **4.7 Observability**

**Structured Logging** (stdout, JSON, secret-scrubbed):
```python
import structlog

structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.stdlib.LoggerFactory(),
)
log = structlog.get_logger()

# Scrub secrets before logging
def scrub_secrets(data: dict) -> dict:
    # Remove API keys, tokens from log payload
    scrubbed = {}
    for k, v in data.items():
        if "key" in k.lower() or "token" in k.lower() or "secret" in k.lower():
            scrubbed[k] = "[REDACTED]"
        else:
            scrubbed[k] = v
    return scrubbed

# Log all key events:
log.info("coo_started", db_path=str(db_path), version="0.6")
log.info("mission_state_changed", mission_id=mid, from_state=old, to_state=new, event=event)
log.info("llm_call", mission_id=mid, agent="Engineer", model="deepseek-v3",
         prompt_tokens=1200, completion_tokens=800, cost_usd=0.0028)
log.warning("mission_backpressure", mission_id=mid, pending=55)
log.error("agent_error", mission_id=mid, agent="Engineer", error_type="timeout")
log.info("sandbox_run", mission_id=mid, artifact_id=art_id, exit_code=0)
log.critical("orchestrator_shutdown", reason="unrecoverable_error")
```

**CLI Metrics** (DB queries):
```bash
coo status                    # Active missions + spent budgets (--all, --json)
coo mission m_42              # Detail: state, cost, loops, messages (--logs, --timeline)
coo logs --mission m_42 --tail 50
coo dlq list
coo dlq show <id>
coo dlq replay <id>           # Single-message replay with confirmation
coo metrics --daily           # Daily/monthly spend
```

**Secret Scrubbing**: Apply to log payloads only. DB stores full message bodies for debugging. `scrub_secrets` must be covered by at least one unit test to confirm keys/tokens do not appear in logged payloads.

**Redaction Flag** (optional but easy):
```sql
ALTER TABLE messages ADD COLUMN redacted BOOLEAN DEFAULT FALSE;
```
Old messages containing sensitive payloads may be overwritten with a redacted stub (`{"redacted": true}`) and `redacted = TRUE` after some retention period (e.g., `--retention-days 30`).

---

### **4.8 Backpressure & Failure Modes**

**Hard Backpressure Rule**:
```python
MAX_PENDING_PER_MISSION = 50  # Configurable per mission

pending = await store.count_pending_messages(mission_id)
if pending > MAX_PENDING_PER_MISSION:
    await state_manager.transition(mission_id, "paused_error", reason="backpressure")
    log.warning("mission_paused_backpressure", mission_id=mission_id, pending=pending)
    return  # Stop scheduling work for this mission
```

**Backpressure UX**: When backpressure triggers, `coo mission <id>` shows:
```
Mission m_42 is paused due to backpressure (55 pending messages).
It will auto-resume when pending < 30, or you can inspect via 
`coo logs --mission m_42` and optionally cancel.
```

**Docker Failure Mode**:
```python
try:
    result = sandbox.run(...)
except DockerError as e:
    log.error("sandbox_unavailable", mission_id=mid, error=str(e))
    await state_manager.transition(mission_id, "failed", reason="sandbox_error")
    # No fallback to unsandboxed execution
```

---

## **5. Build Plan (5 Phases, ~6 Weeks)**

### **Phase 0: Core Infrastructure (4-5 days)**
- ✅ SQLite schema + migrations (with v0.6 amendments)
- ✅ MessageStore async methods (`claim_pending`, `deliver_message`, `reclaim_stale`)
- ✅ Models (Pydantic schemas)
- ✅ Config file skeleton (`models.yaml`, `sandbox.yaml`, `orchestrator.yaml`)
- ✅ CLI skeleton: `coo init-db`, `coo status`
- ✅ First test: `test_message_store.py`
- **Commit**: `git commit -m "Phase 0: Core DB and message bus"`

### **Phase 1: Orchestrator + Dummy Agents (3-4 days)**
- ✅ `orchestrator.py` with asyncio main loop + ThreadPoolExecutor
- ✅ `Agent` base class + `process_stream` generator
- ✅ `DummyCOO`, `DummyEngineer`, `DummyQA` emitting emissions
- ✅ `BudgetTracker` skeleton
- ✅ End-to-end test: mission flow with no LLMs
- ✅ Stale message reclaim implementation
- **Commit**: `git commit -m "Phase 1: Orchestrator + dummy agents"`

### **Phase 2: Sandbox Integration (4-5 days)**
- ✅ Build `coo-sandbox:latest` Dockerfile (Python, pytest, std libs)
- ✅ `sandbox.py` Docker wrapper (`--network none`, resource limits)
- ✅ Orchestrator handles `SANDBOX_EXECUTE` emissions
- ✅ Artifact materialization to bind mount
- ✅ Result artifact storage + RESULT message emission
- ✅ Workspace cleanup implementation
- ✅ Test: Engineer → Sandbox → QA
- **Commit**: `git commit -m "Phase 2: Network-isolated sandbox"`

### **Phase 3: Real LLM Agents + Budget (7-10 days)**
- ✅ `ModelClient` for DeepSeek + GLM (sync HTTP in thread pool)
- ✅ Central token caps enforcement (`max_tokens_per_call`)
- ✅ COO/Engineer/QA prompts via `PromptManager`
- ✅ Prompt file structure (`prompts/<agent>/...`)
- ✅ Cost calculation from API responses
- ✅ **Hard budget enforcement + rollback on exceed** with `BEGIN IMMEDIATE`
- ✅ Global daily/monthly budget tracking
- ✅ Test: budget exceed → rollback verified
- **Commit**: `git commit -m "Phase 3: Real LLM agents + budget safety"`

### **Phase 4: Observability + Hardening (5-7 days)**
- ✅ `structlog` integration with secret scrubbing
- ✅ Timeline events for all major actions
- ✅ CLI commands: `coo mission`, `coo logs`, `coo dlq replay` (moved to v1.0)
- ✅ Approval flow (CEO gate) + CONTROL messages
- ✅ Backpressure hard pause implementation with hysteresis
- ✅ Sandbox crash recovery
- ✅ `scrub_secrets` unit test
- ✅ Critical shutdown logging
- ✅ **Integration tests**: happy path, error path, budget exceed, sandbox failure
- ✅ README + operations guide (derived from this spec)
- **Commit**: `git commit -m "Phase 4: Observability + approval gates"`

### **v1.0 Definition of Done**
- Single mission end-to-end works: CEO → COO → Engineer → Sandbox → QA → COO → Completed
- Budget enforcement tested (simulate exceed → rollback observed)
- Sandbox security verified (`--network none`, non-root, resource limits)
- Crash recovery tested (kill -9 orchestrator → restart → reclaim works)
- CLI UX: create mission, watch logs, inspect DLQ, check budget
- All critical paths covered by at least one integration test
- `scrub_secrets` test passes
- Multi-mission concurrency tested (at least 2 simultaneous missions)
- Load test: 5 concurrent missions with mocked LLMs (verify no DB locks)
- Chaos test: Kill orchestrator mid-mission, restart, verify recovery

**Testing Note**: While the architecture supports multi-mission, it is acceptable to test v1.0 initially in "single active mission" mode until the orchestrator proves stable. Multi-mission is a supported feature, but early testing should focus on correctness over concurrency.

---

## **6. Review Gates for AI Team**

### **When to Pause for ChatGPT (/review-gpt)**
- Agent interface changes (e.g., adding new emission types)
- Orchestrator concurrency model adjustments
- BudgetGuard logic modifications (pre/post call checks)
- Message protocol changes (new kinds, field removals)
- FSM transition table changes

### **When to Pause for Gemini (/review-gemini)**
- Sandbox security policy (network, user privileges, readonly rootfs)
- DB schema (privilege isolation, SQL injection risks)
- Overall architecture (coupling, complexity, over-engineering)
- Docker image supply chain (fat image vs dynamic install)

### **When to Delegate to GLM (/glm)**
- Pydantic model boilerplate
- pytest fixtures and stubs
- CLI argument parsing (click/typer)
- GitHub Actions YAML for CI
- README formatting and examples

---

## **7. Implementation Starter Code (Phase 0)**

**File: `coo/main.py`**
```python
import asyncio
import structlog
from pathlib import Path
from message_store import MessageStore
from budget import BudgetTracker

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

async def main():
    db_path = Path.home() / ".local/share/coo/coo.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    store = MessageStore(db_path)
    budget = BudgetTracker()
    
    await store.initialize()
    log.info("coo_started", db_path=str(db_path), version="0.6")
    
    # TODO: Implement Orchestrator
    # orchestrator = Orchestrator(store, budget, config)
    # await orchestrator.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("coo_shutdown", reason="user_interrupt")
    except Exception as e:
        log.critical("coo_fatal_error", error=str(e))
        raise
```

**File: `coo/message_store.py` (Complete Skeleton)**
```python
import aiosqlite
from pathlib import Path
from datetime import datetime, timedelta

class MessageStore:
    HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes
    
    def __init__(self, db_path: Path, worker_id: str = None):
        self.db_path = db_path
        self.worker_id = worker_id or f"{Path.home().name}_{id(self)}"
    
    async def initialize(self):
        """Create tables if they don't exist"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA synchronous = NORMAL")
            await db.execute("PRAGMA busy_timeout = 5000")
            
            # Create tables from spec
            # ... (all CREATE TABLE statements from §4.1)
            
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
            await db.commit()
            return [dict(row) for row in rows]
    
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
```

---

## **8. Optional Features (v1.1+ Roadmap)**

These are **documented but not implemented** in v1.0:

- **Conversation summarization** (compress older messages)
- **Optional `messages.sequence_number`** + index for strict ordering (explicitly out-of-scope for v1.0)
- **Prometheus metrics endpoint** (`/metrics`)
- **More formal error-recovery workflows** for DLQ
- **Async HTTP clients**: Replace ThreadPoolExecutor with `httpx.AsyncClient`
- **Agent enable/disable CLI**: `coo agent disable Engineer`
- **Backup/restore tooling**: `coo backup`, `coo restore`

---

## **9. Non-Goals (Explicitly Excluded)**

To prevent scope creep, **v1.0 will NOT include**:
- Task DAG or dependency graph
- Conversation summary tables or vector DB
- Alerting subsystem (PagerDuty, Slack)
- Circuit breaker infrastructure (Hystrix-style)
- Config schema migrations (semver config files)
- Multi-worker orchestrators (distributed mode)
- Multi-storage artifact system (S3, etc.)
- Advanced memory retrieval (RAG)
- Web UI
- User authentication / multi-user model
- Horizontal scaling

---

## **10. What Kimi Actually Has To Do (Concise Action List)**

**Critical Path (Do These First):**
1. **Add status column to sandbox_runs table** (from §4.1 schema)
2. **Create config templates** (copy from §10.1 below)
3. **Create Dockerfile.sandbox** (copy from §10.2 below)
4. **Create directory structure** (from §10.3 below)
5. **Implement transactional budget reservation** (§8.1 pattern)
6. **Implement sandbox workspace cleanup** (§9.3)
7. **Implement sandbox crash recovery** (§9.4)
8. **Write scrub_secrets unit test** (§10.1)

**Configuration Templates:**

**File: `config/models.yaml`**
```yaml
version: 1

models:
  deepseek_v3:
    provider: "deepseek"
    base_url: "https://api.deepseek.com/v1"
    api_key_env: "DEEPSEEK_API_KEY"
    max_tokens: 8000
    pricing:
      input_per_1k: 0.00027
      output_per_1k: 0.00110
  
  glm_46:
    provider: "glm"
    base_url: "https://open.bigmodel.cn/api/paas/v4"
    api_key_env: "GLM_API_KEY"
    max_tokens: 4096
    pricing:
      input_per_1k: 0.00010
      output_per_1k: 0.00010

agents:
  COO:
    model: "deepseek_v3"
    max_tokens_per_call: 6000
    temperature: 0.7
    
  Engineer:
    model: "deepseek_v3"
    max_tokens_per_call: 8000
    temperature: 0.3
    
  QA:
    model: "glm_46"
    max_tokens_per_call: 4000
    temperature: 0.2
```

**File: `config/orchestrator.yaml`**
```yaml
orchestrator:
  tick_interval_seconds: 1
  max_concurrent_missions: 5
  heartbeat_timeout_seconds: 300

budgets:
  global:
    daily_limit_usd: 50.00
    monthly_limit_usd: 500.00
  
  default_mission:
    max_cost_usd: 5.00
    max_loops: 20
    safety_margin: 0.95
  
  budget_increase:
    max_requests_per_mission: 3

backpressure:
  max_pending_messages: 50
  resume_threshold: 30
```

**File: `docker/Dockerfile.sandbox`**
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y gcc git && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    requests==2.31.0 \
    numpy==1.26.2 \
    pandas==2.1.4 \
    pydantic==2.5.3 \
    black==23.12.1 \
    flake8==7.0.0

RUN useradd -m -u 1000 -s /bin/bash sandbox
USER 1000:1000
WORKDIR /workspace
```

**Directory Structure:**
```
coo-agent/
├── coo/
│   ├── __init__.py
│   ├── main.py
│   ├── orchestrator.py
│   ├── message_store.py
│   ├── budget.py
│   ├── sandbox.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── dummy_agents.py
│   └── cli.py
├── config/
│   ├── models.yaml
│   ├── sandbox.yaml
│   └── orchestrator.yaml
├── docker/
│   └── Dockerfile.sandbox
├── prompts/  (empty for now)
├── tests/
│   └── unit/
│       └── test_message_store.py
├── pyproject.toml
├── ARCHITECTURE.md (this spec)
└── .gitignore
```

**Prompt File Structure (Phase 3):**
```
prompts/
├── coo/
│   └── planning.md
├── engineer/
│   └── implement.md
└── qa/
    └── review.md
```

---

## **11. Sign-Off**

**Specification Status**: ✅ **APPROVED for implementation**

**Kimi's Assessment**: The v0.6-FINAL amendment pack incorporates all critical feedback from the review cycle. The changes harden budget governance, clarify sandbox security, improve crash recovery, make the CLI/UX behavior explicit, and add missing config/prompt structures. No gaps remain that would block a correct v1.0 implementation. The scope is tightly bounded and achievable in ~6 weeks.

**Claude's Feedback Integration**: The most critical code patterns from the comprehensive review (transactional budget guard, sandbox with status tracking, stale message reclaim, orchestrator main loop) have been incorporated as implementation hints. The week-by-week plan is realistic if followed sequentially.

**Next Action**: 
1. Execute the pre-flight checklist (45 minutes):
   - Create repo and directory structure
   - Copy config templates
   - Copy Dockerfile
   - Write first unit test
   - Initial commit
2. Begin **Phase 0, Day 1**: implement `message_store.py` with complete async methods.

**Build Order**: Follow Phase 0 → Phase 4 sequentially. Do not skip. Do not add features.

**Signed**: Kimi (Primary Engineer)  
**Date**: 2025-11-19