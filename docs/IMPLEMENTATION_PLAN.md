# Phase 4: Observability + Hardening

## Goal Description
Enhance system observability with structured logging (`structlog`) and timeline events. Implement CLI commands for inspection (`coo mission`, `coo logs`). Harden the system with secret scrubbing and integration tests.

## User Review Required
> [!NOTE]
> **CLI Usage**: New commands will be available: `python -m coo.cli mission <id>` and `python -m coo.cli logs <id>`.

## Proposed Changes

### Observability
#### [MODIFY] [coo/main.py](file:///c:/Users/cabra/Projects/COOProject/coo-agent/coo/main.py)
- Configure `structlog` with:
    - JSON renderer.
    - Timestamp, level, logger name.
    - **Secret Scrubbing**: Processor to redact API keys and sensitive data.

#### [MODIFY] [coo/message_store.py](file:///c:/Users/cabra/Projects/COOProject/coo-agent/coo/message_store.py)
- **`log_timeline_event`**: New method to insert into `timeline_events` table.
- Call this method from `Orchestrator` and `Agents` for major lifecycle events (mission start, task complete, budget warning).

### CLI & Operations
#### [MODIFY] [coo/cli.py](file:///c:/Users/cabra/Projects/COOProject/coo-agent/coo/cli.py)
- **`mission <id>`**: Show status, budget usage, and recent timeline.
- **`logs <id>`**: Dump structured logs or timeline events for a mission.
- **`dlq replay <id>`**: Replay a failed message from Dead Letter Queue.

### Hardening
#### [NEW] [tests/unit/test_scrubbing.py](file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/unit/test_scrubbing.py)
- Verify that `structlog` processor correctly redacts secrets from logs.

#### [NEW] [tests/integration/test_full_system.py](file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/integration/test_full_system.py)
- Full integration test running the Orchestrator against a real (or mocked) LLM and Sandbox, verifying the entire lifecycle including timeline events.

## Verification Plan

### Automated Tests
- **`test_scrubbing.py`**: Ensure no secrets leak into logs.
- **`test_full_system.py`**: Verify end-to-end flow with observability checks.

### Manual Verification
- Run `coo mission <id>` on a running mission to verify real-time status.
- Inspect `coo.log` (or stdout) to confirm JSON formatting and redaction.
