# COO Runtime v1.0 — Spec-vs-Code Drift Detection Report (Runtime Only)

**Status**: READ-ONLY Analysis Complete  
**Date**: 2025-12-01  
**Report Type**: Runtime-Only Drift Detection (Focused Scope)  
**Authority**: LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0 → R6.2/R6.3 Fix Packets → R6.4/R6.5 Fix Packs

---

## Scope & Inputs

### Scope Boundaries

This analysis is **strictly limited** to the COO Runtime implementation under `coo_runtime/` and directly-governed runtime modules. The following were analyzed:

- `coo_runtime/runtime/state_machine.py` - FSM implementation
- `coo_runtime/runtime/migration.py` - Migration sequence
- `coo_runtime/runtime/amu_capture.py` - AMU₀ capture
- `coo_runtime/runtime/rollback.py` - Rollback engine
- `coo_runtime/runtime/rollback_log.py` - Rollback log management
- `coo_runtime/runtime/gates.py` - Gate execution
- `coo_runtime/runtime/replay.py` - Replay engine
- `coo_runtime/runtime/freeze.py` - Freeze protocol
- `coo_runtime/runtime/init.py` - Runtime initialization
- `coo_runtime/util/amu0_utils.py` - AMU₀ utilities
- `coo_runtime/util/crypto.py` - Cryptographic operations
- `coo_runtime/util/context.py` - Hardware/context capture
- `coo_runtime/util/subprocess.py` - Pinned subprocess execution
- `coo_runtime/util/questions.py` - QUESTION routing

### Explicitly Excluded (NOT Analyzed for Drift)

- `project_builder/` - Out of scope (not governed by Runtime spec)
- Mission/task orchestrators - Out of scope
- Dev tooling and scaffolding - Out of scope

### Specifications Used

1. **COO Runtime Spec v1.0** (`specs/COO_RUNTIME_SPECIFICATION_v1.0.md`) - Primary
2. **Implementation Packet v1.0** (`impl/IMPLEMENTATION_PACKET_v1.0.md`) - Primary
3. **Alignment Layer v1.4** (`specs/Alignment_Layer_v1.4.md`) - Constitutional authority
4. **R6.2 Fix Packet** (`COO Runtime v1.0 — R6.2 FIX PACKET.md`) - Blocking fixes
5. **R6.3 Fix Packet** (`COO Runtime v1.0 — R6.3 FIX PACKET.md`) - Blocking fixes
6. **R6.4 Fix Packet** (`council_review/COO Runtime v1.0 — R6.4 FIX PACKET.md`) - CSO rulings
7. **R6.5 Fix Pack** (`council_review/COO Runtime v1.0 — R6.5 FIX PACK.md`) - Final binding requirements

---

## Runtime FSM Drift Table

### Canonical FSM (Spec + R6.3 Amendment)

Per COO Runtime Spec v1.0 §3, **as amended by R6.3 B6** (REPLAY state removed, Gate F runs in GATES):

```
INIT → AMENDMENT_PREP → AMENDMENT_EXEC → AMENDMENT_VERIFY → CEO_REVIEW → FREEZE_PREP → FREEZE_ACTIVATED → CAPTURE_AMU0 → MIGRATION_SEQUENCE → GATES → CEO_FINAL_REVIEW → COMPLETE
```

Additional: ERROR state (terminal, reached on any governance violation)

### FSM Comparison

| Spec State | Implemented? | Spec Successors | Implemented Successors | Drift Type | Classification | Notes |
|------------|--------------|-----------------|----------------------|------------|----------------|-------|
| INIT | ✅ Yes | AMENDMENT_PREP, ERROR | AMENDMENT_PREP, ERROR | None | — | Compliant |
| AMENDMENT_PREP | ✅ Yes | AMENDMENT_EXEC, ERROR | AMENDMENT_EXEC, ERROR | None | — | Compliant |
| AMENDMENT_EXEC | ✅ Yes | AMENDMENT_VERIFY, ERROR | AMENDMENT_VERIFY, ERROR | None | — | Compliant |
| AMENDMENT_VERIFY | ✅ Yes | CEO_REVIEW, ERROR | CEO_REVIEW, ERROR | None | — | Compliant |
| CEO_REVIEW | ✅ Yes | FREEZE_PREP, ERROR | FREEZE_PREP, ERROR | None | — | Compliant |
| FREEZE_PREP | ✅ Yes | FREEZE_ACTIVATED, ERROR | FREEZE_ACTIVATED, ERROR | None | — | Compliant |
| FREEZE_ACTIVATED | ✅ Yes | CAPTURE_AMU0, ERROR | CAPTURE_AMU0, ERROR | None | — | Compliant |
| CAPTURE_AMU0 | ✅ Yes | MIGRATION_SEQUENCE, ERROR | MIGRATION_SEQUENCE, ERROR | None | — | Compliant |
| MIGRATION_SEQUENCE | ✅ Yes | GATES, ERROR, CAPTURE_AMU0† | GATES, ERROR, CAPTURE_AMU0 | None | — | †Rollback transition per spec |
| GATES | ✅ Yes | CEO_FINAL_REVIEW, ERROR, CAPTURE_AMU0† | CEO_FINAL_REVIEW, ERROR, CAPTURE_AMU0 | None | — | †Rollback transition per spec |
| **REPLAY** | ❌ No | CEO_FINAL_REVIEW, ERROR | *Not Implemented* | **Removed** | **SPEC_OUT_OF_DATE** | R6.3 B6: REPLAY removed, Gate F runs in GATES |
| CEO_FINAL_REVIEW | ✅ Yes | COMPLETE, ERROR | COMPLETE, ERROR | None | — | Compliant |
| COMPLETE | ✅ Yes | [] (terminal) | [] | None | — | Compliant |
| ERROR | ✅ Yes | [] (terminal) | [] | None | — | Compliant |

### FSM Drift Summary

**REPLAY State Removal (SPEC_OUT_OF_DATE)**:
- **Spec Reference**: COO Runtime Spec v1.0 §3 lists REPLAY as a canonical state
- **Amendment**: R6.3 B6 removes REPLAY state; Gate F runs during GATES state
- **Implementation**: Code correctly implements R6.3 amendment (no REPLAY state)
- **Classification**: **SPEC_OUT_OF_DATE** - Base spec should be updated to reflect R6.3 amendment

---

## Migration Sequence Drift Table

### Canonical Migration Sequence (Implementation Packet v1.0 §9)

| Spec Step # | Step Name | Required Preconditions | Expected Postconditions |
|-------------|-----------|----------------------|------------------------|
| 1 | Create canonical coo/ tree | MIGRATION_SEQUENCE state | coo/ directory exists |
| 2 | Port PB code → coo/ | coo/ exists | All PB code copied deterministically |
| 3 | Update test imports to coo.* | Code ported | Tests reference coo.* |
| 4 | Run full test suite (Snapshot A) | Imports updated | Tests pass |
| 5 | Update production imports (PB → coo) | Tests pass | Production code references coo.* |
| 6 | Delete project_builder/ | Production imports updated | PB directory removed |
| 7 | Run full test suite (Snapshot B) | PB deleted | Tests pass post-deletion |

### Migration Comparison

| Spec Step # | Spec Step Name | Impl Step # | Impl Function/Module | Drift Type | Classification | Notes |
|-------------|----------------|-------------|---------------------|------------|----------------|-------|
| 1 | Create canonical coo/ tree | 1 | `_create_coo_tree()` | None | — | Compliant |
| 2 | Port PB code → coo/ | 2 | `_port_code()` | None | — | Deterministic sorted traversal ✓ |
| 3 | Update test imports | 3 | `_update_imports()` | None | — | Pure AST per R6.3 A6 ✓ |
| 4 | Run test suite (Snapshot A) | 4 | `_run_tests()` | None | — | Uses pinned subprocess ✓ |
| 5 | Update production imports | — | *Combined with Step 3* | **Combined** | **AMBIGUOUS** | Unclear if separate step needed |
| 6 | Delete project_builder/ | 5 | `_delete_project_builder()` | None | — | Compliant |
| 7 | Run test suite (Snapshot B) | — | **NOT IMPLEMENTED** | **Missing** | **CODE_OUT_OF_SPEC** | Critical: No post-deletion test run |

### Migration Drift Details

**Missing Step 7: Post-Deletion Test Suite (CODE_OUT_OF_SPEC)**:
- **Spec Reference**: Implementation Packet v1.0 §9, Step 7: "Run full test suite (Snapshot B)"
- **Required**: Tests MUST run after PB deletion to verify coo/ imports work standalone
- **Implementation**: `execute_migration_phase_1()` in [`migration.py`](coo_runtime/runtime/migration.py:25) does NOT call `_run_tests()` after deletion
- **Impact**: Migration may succeed but leave broken imports undetected
- **Classification**: **CODE_OUT_OF_SPEC** — Code must add post-deletion test run

**Combined Steps 3/5 (AMBIGUOUS)**:
- **Spec Reference**: Implementation Packet §9 lists separate "Update test imports" and "Update production imports" steps
- **Implementation**: Single `_update_imports()` transforms all imports (test + production) together
- **Impact**: Semantically equivalent if coo/* is used everywhere
- **Classification**: **AMBIGUOUS** — May be acceptable; CSO guidance needed

---

## Runtime Invariant Drift

### A. AMU₀ Integrity

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Single canonical verification | R6.5 A1 | `verify_amu0_complete()` in [`amu0_utils.py`](coo_runtime/util/amu0_utils.py:118) | ✅ COMPLIANT | All verification routes through single function |
| Canonical hash exclusions | R6.3 A2 | `EXCLUDED_FROM_HASH` set | ✅ COMPLIANT | Excludes rollback_log.*, signature.sig, *.tmp |
| AMU₀ ID derivation | R6.3 A3 | `derive_amu0_id()` | ✅ COMPLIANT | First 16 hex chars of canonical hash |
| Atomic capture | R6.5 A3 | Temp directory + atomic rename | ✅ COMPLIANT | `os.rename()` from temp to final |
| Deep replay trace | R6.5 A4 | `external_trace.jsonl` capture | ✅ COMPLIANT | Included in canonical hash |

### B. Rollback Integrity

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Hash-chained log | R6.2 F1 | Entry hash chain in [`rollback_log.py`](coo_runtime/runtime/rollback_log.py:51) | ✅ COMPLIANT | previous_hash + entry_hash |
| Pinned timestamp | R6.2 F1 | `_get_pinned_time()` | ✅ COMPLIANT | Uses mock_time from pinned_context |
| Atomic append | R6.3 A6 | Write to .tmp + atomic rename | ✅ COMPLIANT | Both log and sig atomically promoted |
| Bounded size | R6.5 C2 | `MAX_ROLLBACK_ENTRIES = 1000` | ✅ COMPLIANT | Fail-closed on full |
| Signature verification | R6.5 C1/C2 | Signature.verify_data() | ✅ COMPLIANT | Full log signed + verified |

### C. Hardware Pinning

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Unified capture function | R6.4 D1 | `capture_hardware_context()` in [`context.py`](coo_runtime/util/context.py:18) | ✅ COMPLIANT | Single function for all capture |
| Kernel version required | R6.4 D2 | Fail-closed if missing | ✅ COMPLIANT | GovernanceError on empty |
| Microcode sentinel | R6.4 D2 | "MICROCODE_UNKNOWN" | ✅ COMPLIANT | Deterministic sentinel, not failure |
| Hardware verification | R6.5 D2 | `_verify_hardware_context()` | ✅ COMPLIANT | Byte-equality comparison |

### D. Subprocess Isolation

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Exclusive subprocess API | R6.5 F1 | `run_pinned_subprocess()` in [`subprocess.py`](coo_runtime/util/subprocess.py:17) | ✅ COMPLIANT | Wrapper enforces pinned env |
| Pinned PATH | R6.3 E2 | `PINNED_PATH = "/usr/bin:/bin"` | ✅ COMPLIANT | Fixed, deterministic |
| Environment override | R6.5 F1 | `kwargs.pop('env')` | ✅ COMPLIANT | Prevents env pollution |
| Time pinning verification | R6.5 F2 | `_verify_time_pinning()` | ✅ COMPLIANT | 1.1s tolerance |

### E. Signature & Key Management

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Unified API | R6.5 G1 | `Signature.sign_data()`, `Signature.verify_data()` | ✅ COMPLIANT | Single class for all operations |
| Memory-resident keys | R6.5 G2 | `load_keys()` + module-level storage | ✅ COMPLIANT | Keys loaded once at init |
| Path rejection | R6.5 G2 | `private_key_path` parameter rejected | ✅ COMPLIANT | CryptoError if path provided |
| Env-only key resolution | R6.5 G2 | `CEO_PRIVATE_KEY_PATH`, `CEO_PUBLIC_KEY_PATH` | ✅ COMPLIANT | Environment variables only |

### F. QUESTION Routing

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Explicit QUESTION mapping | R6.5 H1 | `QuestionType` enum in [`questions.py`](coo_runtime/util/questions.py:7) | ✅ COMPLIANT | 13 question types defined |
| Central raise function | R6.5 H1 | `raise_question()` | ✅ COMPLIANT | Consistent GovernanceError format |
| Coverage | R6.5 H1 | All invariant failures | ✅ COMPLIANT | AMU₀, rollback, hardware, replay, etc. |

### G. Determinism Invariants

| Requirement | Spec Reference | Implementation | Status | Notes |
|------------|----------------|----------------|--------|-------|
| Runtime initialization | R6.5 E1 | `initialize_runtime()` in [`init.py`](coo_runtime/runtime/init.py:19) | ✅ COMPLIANT | Single entry point, idempotent |
| Deprecated helpers removed | R6.5 E2 | `enforce_pinned_context_or_fail` removed | ✅ COMPLIANT | Comment confirms removal |
| **Timestamp in sig metadata** | Determinism Contract | `datetime.utcnow()` in [`crypto.py:177`](coo_runtime/util/crypto.py:177) | ⚠️ **MINOR ISSUE** | Uses wall-clock time for metadata |

---

## Code Quality Issues (Non-Spec)

The following issues were observed but are not spec violations:

1. **Duplicated Code in state_machine.py**: Lines 197-400 appear to be a copy of lines 1-196. This is a code hygiene issue.

2. **Variable Reference Before Assignment**: In `load_checkpoint()` method, the first code block (line 192) references `data` before it's defined. The second block (line 387-388) shows the fix.

---

## Summary of Drift Findings

### Critical (CODE_OUT_OF_SPEC)

| Finding | Spec Reference | File | Classification |
|---------|---------------|------|----------------|
| Missing post-deletion test run | Impl Packet §9 Step 7 | [`migration.py:25`](coo_runtime/runtime/migration.py:25) | **CODE_OUT_OF_SPEC** |

### Specification Updates Needed (SPEC_OUT_OF_DATE)

| Finding | Current Spec | Amendment | Classification |
|---------|-------------|-----------|----------------|
| REPLAY state listed | Runtime Spec §3 | R6.3 B6 removes REPLAY | **SPEC_OUT_OF_DATE** |

### Requires Clarification (AMBIGUOUS)

| Finding | Spec Reference | Implementation | Classification |
|---------|---------------|----------------|----------------|
| Test/production import steps combined | Impl Packet §9 Steps 3 & 5 | Single `_update_imports()` | **AMBIGUOUS** |

### Minor Issues (Non-Blocking)

| Finding | Location | Impact |
|---------|----------|--------|
| Wall-clock timestamp in signature metadata | `crypto.py:177` | Metadata non-determinism (not signature itself) |

---

## Recommendations (No Code Changes)

### Decisions Required

1. **Post-Deletion Test Run (Critical)**
   - **Decision**: Code MUST be updated to add `_run_tests()` call after `_delete_project_builder()`
   - **Owner**: Development Team
   - **Spec**: Implementation Packet v1.0 §9 Step 7

2. **Combined Import Steps**
   - **Decision**: CSO/CEO to clarify whether single AST pass satisfies both Steps 3 and 5
   - **Owner**: CSO
   - **Note**: Current implementation is semantically correct but structurally different

### Specification Updates Needed

1. **COO Runtime Spec v1.0 §3**
   - Update FSM diagram to remove REPLAY state per R6.3 B6
   - Add note that Gate F runs during GATES state

### No Action Required

- FSM transitions: Fully compliant with R6.3-amended spec
- AMU₀ integrity: All R6.5 requirements implemented
- Rollback integrity: All R6.5 requirements implemented
- Hardware pinning: All R6.4/R6.5 requirements implemented
- Subprocess isolation: All R6.5 requirements implemented
- Key management: All R6.5 requirements implemented
- QUESTION routing: All R6.5 requirements implemented

---

## Appendix: Critique of Previous Drift Report

The previous drift report (`DRIFT_REPORT_FSM_MIGRATION.md`) violated the scope boundaries:

1. **Scope Violation**: Analyzed `project_builder/orchestrator/fsm.py` which is NOT part of the governed COO Runtime
2. **Incorrect Architectural Conclusion**: Concluded there is "fundamental architecture mismatch" when Project Builder is simply a separate, ungoverned system
3. **False Drift Findings**: Listed Project Builder task states (pending, executing, review, etc.) as "unauthorized" when they're out of scope

The Project Builder orchestrator is a **separate workload system** processed by the COO Runtime, not part of the Runtime itself. The Runtime FSM governs the migration/deployment lifecycle, while Project Builder manages task execution workflows. These are orthogonal concerns.

---

**Report Classification**: Constitutional Runtime Analysis  
**Report Status**: COMPLETE  
**Next Steps**: Address CODE_OUT_OF_SPEC finding (missing post-deletion test run)