# COO Runtime v1.0 — Spec-vs-Code Drift Detection Report
**Status**: READ-ONLY Analysis Complete  
**Date**: 2025-12-01  
**Authority**: LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0

## Executive Summary

This report documents systematic drift between the canonical COO Runtime v1.0 specification and the actual implementation. The analysis reveals **significant architectural divergence** between the specified deterministic FSM and the implemented Project Builder orchestrator system, indicating that the current codebase represents a **different system architecture** than what the specifications mandate.

**Critical Finding**: The implemented system appears to be a **Project Builder orchestrator** rather than the **COO Runtime v1.0** as specified. The FSM states, migration sequence, and governance model fundamentally differ from the canonical specifications.

## Canonical FSM Analysis (Per Specifications)

### Specified FSM States (COO Runtime Spec v1.0 §3)
```
INIT → AMENDMENT_PREP → AMENDMENT_EXEC → AMENDMENT_VERIFY → CEO_REVIEW → FREEZE_PREP → FREEZE_ACTIVATED → CAPTURE_AMU0 → MIGRATION_SEQUENCE → GATES → REPLAY → CEO_FINAL_REVIEW → COMPLETE
```

### Canonical Migration Sequence (Implementation Packet v1.0 §9)
1. **Atomic Block (Steps 1-7)**:
   - Create canonical coo/ tree
   - Deterministically port PB code → coo/
   - Update test imports to coo.*
   - Run full test suite (Snapshot A)
   - Update production imports (PB → coo)
   - Delete project_builder/ directory
   - Run full test suite (Snapshot B)

2. **Gate Sequence** (Ordered, Deterministic):
   - Gate A — Repo Unification Integrity
   - Gate B — Deterministic Modules
   - Gate D — Sandbox Security
   - Gate C — Test Suite Integrity
   - Gate E — Governance Integrity
   - Gate F — Deterministic Replay

## Implemented FSM Analysis

### Project Builder Orchestrator FSM (project_builder/orchestrator/fsm.py)
The implemented system uses a **task-level FSM** with states:
- `pending` → `executing` → `review` → `approved`/`failed_terminal`/`repair_retry`/`skipped`
- Additional mission states: `created`, `planning`, `executing`, `reviewing`, `paused_*`, `completed`, `failed`

### COO Runtime FSM (coo_runtime/runtime/state_machine.py)
The implemented COO Runtime FSM shows **spec compliance** with states:
```
INIT → AMENDMENT_PREP → AMENDMENT_EXEC → AMENDMENT_VERIFY → CEO_REVIEW → FREEZE_PREP → FREEZE_ACTIVATED → CAPTURE_AMU0 → MIGRATION_SEQUENCE → GATES → CEO_FINAL_REVIEW → COMPLETE
```
**Note**: REPLAY state removed per R6.3 fix (B6), Gate F runs within GATES state.

## Major Drift Findings

### 1. System Architecture Mismatch

| Aspect | Canonical Spec | Implemented | Drift Type | Classification |
|--------|---------------|-------------|------------|----------------|
| **Primary System** | COO Runtime v1.0 | Project Builder Orchestrator | **Extra System** | **CODE_OUT_OF_SPEC** |
| **FSM Level** | Runtime-level FSM | Task-level FSM | **Wrong Abstraction** | **CODE_OUT_OF_SPEC** |
| **Governance Model** | CEO-only authority | Multi-agent orchestration | **Governance Leak** | **CODE_OUT_OF_SPEC** |

### 2. FSM State Drift

| Spec State | Implemented? | Spec Successors | Implemented Successors | Drift Type | Classification |
|------------|--------------|-----------------|----------------------|------------|----------------|
| `INIT` | ✅ | `AMENDMENT_PREP`, `ERROR` | `AMENDMENT_PREP`, `ERROR` | None | None |
| `AMENDMENT_PREP` | ✅ | `AMENDMENT_EXEC`, `ERROR` | `AMENDMENT_EXEC`, `ERROR` | None | None |
| `AMENDMENT_EXEC` | ✅ | `AMENDMENT_VERIFY`, `ERROR` | `AMENDMENT_VERIFY`, `ERROR` | None | None |
| `AMENDMENT_VERIFY` | ✅ | `CEO_REVIEW`, `ERROR` | `CEO_REVIEW`, `ERROR` | None | None |
| `CEO_REVIEW` | ✅ | `FREEZE_PREP`, `ERROR` | `FREEZE_PREP`, `ERROR` | None | None |
| `FREEZE_PREP` | ✅ | `FREEZE_ACTIVATED`, `ERROR` | `FREEZE_ACTIVATED`, `ERROR` | None | None |
| `FREEZE_ACTIVATED` | ✅ | `CAPTURE_AMU0`, `ERROR` | `CAPTURE_AMU0`, `ERROR` | None | None |
| `CAPTURE_AMU0` | ✅ | `MIGRATION_SEQUENCE`, `ERROR` | `MIGRATION_SEQUENCE`, `ERROR` | None | None |
| `MIGRATION_SEQUENCE` | ✅ | `GATES`, `ERROR`, `CAPTURE_AMU0` | `GATES`, `ERROR`, `CAPTURE_AMU0` | None | None |
| `GATES` | ✅ | `CEO_FINAL_REVIEW`, `ERROR`, `CAPTURE_AMU0` | `CEO_FINAL_REVIEW`, `ERROR`, `CAPTURE_AMU0` | None | None |
| `REPLAY` | ❌ | `CEO_FINAL_REVIEW`, `ERROR` | **Removed** | **Missing State** | **SPEC_OUT_OF_DATE** |
| `CEO_FINAL_REVIEW` | ✅ | `COMPLETE`, `ERROR` | `COMPLETE`, `ERROR` | None | None |
| `COMPLETE` | ✅ | [] | [] | None | None |

### 3. Migration Sequence Drift

| Spec Step # | Spec Step Name | Implemented Step # | Implemented Function/Module | Drift Type | Classification |
|-------------|----------------|-------------------|----------------------------|------------|----------------|
| 1 | Create canonical coo/ tree | 1 | `_create_coo_tree()` in migration.py | None | None |
| 2 | Port PB code → coo/ | 2 | `_port_code()` with deterministic sorting | None | None |
| 3 | Update test imports | 3 | `_update_imports()` with AST transformation | None | None |
| 4 | Run test suite (Snapshot A) | 4 | `_run_tests()` with pinned subprocess | None | None |
| 5 | Update production imports | 5 | `_update_imports()` (combined step) | **Combined** | **AMBIGUOUS** |
| 6 | Delete project_builder/ | 6 | `_delete_project_builder()` | None | None |
| 7 | Run test suite (Snapshot B) | **Missing** | **Not implemented** | **Missing Step** | **CODE_OUT_OF_SPEC** |

### 4. Project Builder Orchestrator States (Extra States)

The implemented Project Builder system introduces **unauthorized states**:

| State | Description | Classification |
|-------|-------------|----------------|
| `planning` | Mission planning phase | **CODE_OUT_OF_SPEC** |
| `reviewing` | Code review phase | **CODE_OUT_OF_SPEC** |
| `paused_error` | Backpressure pause | **CODE_OUT_OF_SPEC** |
| `repair_retry` | Task repair attempts | **CODE_OUT_OF_SPEC** |
| `failed_terminal` | Task failure state | **CODE_OUT_OF_SPEC** |

### 5. Invariant Drift Findings

#### Determinism Requirements
- **Spec Requirement**: Byte-identical output under identical state (COO Runtime Spec §2)
- **Implementation**: Project Builder uses `datetime.utcnow()` in multiple locations without deterministic time pinning
- **Classification**: **CODE_OUT_OF_SPEC**

#### AMU₀/Rollback Guarantees
- **Spec Requirement**: CEO MUST cryptographically sign AMU₀ (COO Runtime Spec §8)
- **Implementation**: AMU₀ capture and signing implemented correctly in `coo_runtime/runtime/amu_capture.py`
- **Classification**: **None** (Compliant)

#### Hardware Capture Requirements
- **Spec Requirement**: Real hardware context capture (R6.3 B1)
- **Implementation**: Hardware context capture implemented in `capture_hardware_context()`
- **Classification**: **None** (Compliant)

#### Governance Boundaries
- **Spec Requirement**: COO Runtime = mechanical enforcement only (COO Runtime Spec §1.2)
- **Implementation**: Project Builder orchestrator makes routing decisions, validates agents, manages budgets
- **Classification**: **CODE_OUT_OF_SPEC**

## Detailed Code Analysis

### Project Builder Orchestrator (Non-Compliant System)
```python
# project_builder/orchestrator/fsm.py - Task-level FSM
def start_task_execution(conn: sqlite3.Connection, mission_id: str, task_id: str, tokenizer_id: str, now: datetime) -> None:
    # Uses datetime.utcnow() - non-deterministic
    check_state(conn, task_id, ("pending", "repair_retry"))
    # Task-level state management, not runtime-level
```

### COO Runtime (Compliant Implementation)
```python
# coo_runtime/runtime/state_machine.py - Runtime-level FSM
class RuntimeFSM:
    def transition_to(self, next_state: RuntimeState) -> None:
        # Strict linear progression enforcement
        if next_state not in self._transitions[self.__current_state]:
            self._force_error(f"Invalid transition attempted: {self.__current_state} -> {next_state}")
```

## Recommendations

### Immediate Actions Required

1. **Architecture Decision**: 
   - **Option A**: Abandon Project Builder orchestrator and implement pure COO Runtime v1.0
   - **Option B**: Update specifications to reflect the Project Builder architecture
   - **Classification**: **CEO-level decision required**

2. **Determinism Fixes**:
   - Replace all `datetime.utcnow()` calls with pinned time from context
   - Implement deterministic RNG seeding
   - **Classification**: **CODE_OUT_OF_SPEC**

3. **Missing Migration Step**:
   - Implement second test suite execution after PB deletion
   - **Classification**: **CODE_OUT_OF_SPEC**

4. **Governance Leak Remediation**:
   - Remove agent routing logic from Project Builder
   - Consolidate all authority in CEO-only decision points
   - **Classification**: **CODE_OUT_OF_SPEC**

### Specification Updates Needed

1. **REPLAY State Removal**: Specifications should be updated to reflect that Gate F runs within GATES state
2. **Migration Sequence**: Clarify whether production import updates should be combined with test import updates

## Risk Assessment

| Risk Level | Description | Impact |
|------------|-------------|---------|
| **CRITICAL** | Architecture mismatch between spec and implementation | **System invalidation** |
| **HIGH** | Missing deterministic time pinning | **Non-reproducible builds** |
| **HIGH** | Missing second test suite execution | **Migration integrity compromise** |
| **MEDIUM** | Governance leakage in orchestrator | **Authority boundary violation** |

## Conclusion

The current implementation represents a **fundamental architectural divergence** from the canonical COO Runtime v1.0 specification. While the COO Runtime implementation (`coo_runtime/`) shows strong compliance with the specified FSM and migration sequence, the primary system appears to be a **Project Builder orchestrator** that operates under different governance and state management principles.

**Critical Decision Required**: The organization must choose between:
1. **Reimplementing** the system according to COO Runtime v1.0 specifications, or
2. **Updating the specifications** to legitimize the current Project Builder architecture

This decision requires CEO-level approval as it impacts the fundamental constitutional architecture of the LifeOS governance system.

---
**Report Generated**: 2025-12-01 00:51:52 UTC  
**Classification**: Constitutional Architecture Analysis  
**Next Action**: CEO Review and Architecture Decision