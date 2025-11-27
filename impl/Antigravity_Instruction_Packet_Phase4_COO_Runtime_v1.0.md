# Antigravity Instruction Packet

**Phase 4 Build — COO Runtime v1.0 + PB→COO Migration**

**Authority Chain:**  
LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Pack v1.0 → this Instruction Packet.

This packet tells you **exactly what to build and in what order**.  
You MUST treat all higher-level specs as non-negotiable.

---

## 0. Scope

You are to:

1. Implement the **COO Runtime v1.0** as specified in `COO Runtime Spec v1.0`.
    
2. Implement all mechanisms described in `Implementation Pack v1.0`.
    
3. Prepare the codebase for a **deterministic PB→COO migration** governed by `Alignment Layer v1.4`.
    

You are **not** being asked to:

- Change LifeOS v1.1
    
- Change Alignment Layer v1.4
    
- Change the Council process
    
- Make governance decisions
    

All work is purely mechanical.

---

## 1. Preconditions

Before starting:

1. Ensure the repository is clean:
    
    - No uncommitted changes
        
    - Main branch is up to date
        
2. Create a dedicated feature branch:
    
    - `feature/coo-runtime-v1.0`
        
3. Confirm you have the following documents locally:
    
    - `LifeOS_v1.1_Core_Specification.md`
        
    - `Alignment_Layer_v1.4.md`
        
    - `COO_Runtime_Spec_v1.0.md`
        
    - `Implementation_Pack_v1.0.md`
        

All implementation MUST follow the Implementation Pack’s directory structure and behaviour.

---

## 2. Phase 1 — Directory & Skeleton Setup

Create the following directory tree, exactly as defined:

`coo_runtime/     runtime/         __init__.py         state_machine.py         amendment_engine.py         lint_engine.py         governance_leak_scanner.py         freeze.py         amu_capture.py         migration.py         gates.py         replay.py         rollback.py         logging.py      manifests/         tools_manifest.json         environment_manifest.json         hardware_manifest.json         sandbox_digest.txt         freeze_manifest.json      tests/         test_determinism.py         test_migration.py         test_replay.py         test_governance_integrity.py         test_sandbox_security.py      scripts/         apply_amendments.py         run_lint.py         run_scanner.py         run_tests.py         run_replay.py         run_migration.py         run_rollback.py      reference/         phase3_reference_mission.json`

Initial state:

- All `.py` files may be empty or contain minimal stubs.
    
- Manifests may be placeholder JSON with the correct keys but empty values.
    
- `phase3_reference_mission.json` may be a placeholder until defined by the CEO/author.
    

Do **not** invent behaviours; fill them in following the later phases.

Commit this initial skeleton once created.

---

## 3. Phase 2 — Manifests & Environment Lock

Implement support for all required manifests.

### 3.1 `manifests/tools_manifest.json`

Implement:

- A JSON structure listing:
    
    - Tool name
        
    - Version
        
    - SHA256 of the built binary or image
        
    - Build toolchain info
        

You must also implement logic (in `runtime/freeze.py` or a helper) to:

- Compute SHA256 of each tool binary/container image.
    
- Compare against `tools_manifest.json`.
    
- Return PASS/FAIL deterministically.
    

### 3.2 `manifests/environment_manifest.json`

Populate with:

- OS name & version
    
- Kernel version
    
- Python version
    
- Locale
    
- Relevant env vars (PATH, etc.)
    

Implement a function to:

- Capture current environment
    
- Compare to manifest
    
- Return PASS/FAIL
    

### 3.3 `manifests/hardware_manifest.json`

Populate with:

- CPU model / ID
    
- Microcode version
    
- NUMA topology
    
- Filesystem type for the runtime directory
    
- Virtualization flags
    

Implement a function to:

- Capture hardware state (within reasonable limits)
    
- Compare against manifest
    
- Return PASS/FAIL
    

### 3.4 `manifests/sandbox_digest.txt`

Single-line SHA256 of the OCI sandbox image.

Implement a check to:

- Inspect the image used for the runtime
    
- Compute digest
    
- Compare with this file
    
- Return PASS/FAIL
    

### 3.5 `manifests/freeze_manifest.json`

This is generated **at Freeze time** by the runtime; you do not pre-populate it manually.  
Implement data structure & write logic; leave contents to runtime logic implemented later.

Commit once manifests support and comparison logic are in place.

---

## 4. Phase 3 — Core Runtime Components

Implement each file in `coo_runtime/runtime/` according to COO Runtime Spec v1.0 and Implementation Pack v1.0.

### 4.1 `state_machine.py`

Implement the FSM with states:

`INIT AMENDMENT_PREP AMENDMENT_EXEC AMENDMENT_VERIFY CEO_REVIEW FREEZE_PREP FREEZE_ACTIVATED CAPTURE_AMU0 MIGRATION_SEQUENCE GATES REPLAY CEO_FINAL_REVIEW COMPLETE ERROR`

Requirements:

- Transitions must be explicit and deterministic.
    
- No implicit fallthrough logic.
    
- Any invalid transition → ERROR.
    

### 4.2 `amendment_engine.py`

Implement:

- Deterministic amendment application as described:
    
    - Deterministic anchor resolution
        
    - Error on missing/ambiguous anchors
        
    - Application order sorted by amendment ID
        

Inputs:

- Amendment protocol file (`amendment_protocol_v1.0.md`)
    
- Amendment instruction set
    
- Original PB/IP docs
    

Outputs:

- Amended PB/IP
    
- `amendment_log.json`
    
- `amendment_diff.patch`
    

### 4.3 `lint_engine.py`

Implement the constitutional lint:

- Checks required invariants are present (subordination, determinism, QUESTION routing).
    
- Checks forbidden constructs per ruleset.
    
- Outputs a deterministic JSON report.
    

### 4.4 `governance_leak_scanner.py`

Implement the scanner using:

- The rule set defined in Alignment Layer v1.4.
    
- A rules file (e.g., `governance_scan_rules.json`) that is SHA256-pinned.
    

The scanner MUST:

- Support both exact-match and pattern-based checks.
    
- Emit PASS/FAIL and detailed violations in deterministic JSON.
    

### 4.5 `freeze.py`

Implement:

- Pre-freeze quiescence:
    
    - Halt async jobs
        
    - Close FDs
        
    - Ensure no pending writes
        
- Tool + environment + hardware verification
    
- Setting `FREEZE = TRUE` in a runtime state location
    

### 4.6 `amu_capture.py`

Implement:

- Filesystem snapshot
    
- DB dump (your DB tech of choice, but deterministic export required)
    
- Manifest snapshots
    
- Sandbox digest
    
- Hardware snapshot
    

Outputs:

- A directory representing AMU₀.
    
- A metadata file with SHA256s for each component.
    

### 4.7 `migration.py`

Implement:

- Canonical PB→COO migration sequence:
    
    - Deterministic porting of modules
        
    - Import rewrites
        
    - Deletion of `project_builder/`
        
    - Two test suite runs (before and after deletion)
        

### 4.8 `gates.py`

Implement:

- Gate A–F checks, ordered as per the spec.
    
- A single function `run_all_gates()` that:
    
    - Executes gates in correct order
        
    - Stops on first failure
        
    - Returns overall status + details
        

### 4.9 `replay.py`

Implement:

- The deterministic replay harness:
    
    - Freeze context (seed, time, env, hardware checks)
        
    - Run mission twice
        
    - Compare outputs, FSM logs, DB logs
        

### 4.10 `rollback.py`

Implement:

- Restoration from AMU₀:
    
    - Restore FS snapshot
        
    - Restore DB dump
        
    - Restore manifests
        
    - Re-validate CEO signature on AMU₀
        

### 4.11 `logging.py`

Implement:

- A deterministic logger that:
    
    - Emits JSON logs
        
    - Includes `sequence_id`, config SHA, env SHA
        
    - Is stable across runs
        

Commit when all core components have stubs or complete implementations, plus minimal tests that import and call them.

---

## 5. Phase 4 — Scripts

Implement the scripts in `coo_runtime/scripts/` as thin, deterministic wrappers around runtime modules.

For each:

- `apply_amendments.py`
    
- `run_lint.py`
    
- `run_scanner.py`
    
- `run_tests.py`
    
- `run_replay.py`
    
- `run_migration.py`
    
- `run_rollback.py`
    

Requirements:

- No business logic; just argument parsing + calling the relevant runtime functions.
    
- Exit codes MUST map to PASS/FAIL.
    
- All output is via the logging module.
    

---

## 6. Phase 5 — Test Suite Implementation

Populate `coo_runtime/tests/` with tests that:

### 6.1 `test_determinism.py`

- Verify repeated runs produce identical artefacts and logs under identical context.
    
- Exercise at least:
    
    - amendment engine
        
    - migration engine
        
    - replay engine
        

### 6.2 `test_migration.py`

- Simulate a PB→COO migration on a test tree.
    
- Assert correct structure and no PB imports remain.
    

### 6.3 `test_replay.py`

- Exercise the replay harness with a mock mission.
    
- Verify mismatch triggers correct failure logic.
    

### 6.4 `test_governance_integrity.py`

- Validate governance-leak scanner and lint outputs, including edge cases.
    

### 6.5 `test_sandbox_security.py`

- Validate sandbox digest checks, including mismatch scenarios.
    

All tests MUST be deterministic and order-stable. No use of random or time without explicit mocking.

---

## 7. Phase 6 — Integration with PB / Existing Codebase

You must integrate the above runtime with the existing PB/Antigravity structure without violating any invariants.

Steps:

1. Identify where PB Spec v0.9 and Implementation Packet v0.9.7 live in the repo.
    
2. Wire `apply_amendments.py` to operate on these actual files.
    
3. Wire `run_migration.py` to perform a dry-run migration in a temporary workspace.
    
4. Ensure no scripts mutate main branch state without explicit invocation and guardrails.
    

At this stage, you are building capabilities, not executing production migration.

---

## 8. Phase 7 — Dry-Run Validation (Non-Production)

Once all components exist:

1. Run:
    
    - `apply_amendments.py` on PB and IP copies
        
    - `run_lint.py`
        
    - `run_scanner.py`
        
2. Verify that:
    
    - Tools manifest verification works
        
    - Freeze prep can be invoked in a no-op or mocked context
        
    - AMU₀ capture can run against a test environment
        
3. Run `run_migration.py` against a test tree (not the real PB tree) and confirm:
    
    - Gates run
        
    - Replay runs
        
    - Rollback can be invoked
        
    - Logs are generated
        

Do **not** execute a real PB→COO migration until explicitly instructed.

---

## 9. Deliverables Back to CEO/Chair

When Phase 4 build is complete, you MUST deliver:

1. The updated repository branch (`feature/coo-runtime-v1.0`) with:
    
    - All runtime modules implemented
        
    - All manifests and scripts in place
        
    - All tests written and passing locally
        
2. A short text report containing:
    
    - List of files added/modified
        
    - Summary of how each runtime module is wired
        
    - Any implementation assumptions or technical notes
        
    - How to run:
        
        - Amendments
            
        - Lint & scanner
            
        - Tests
            
        - Migration dry-run
            
        - Replay
            
        - Rollback
            
3. A bundle of:
    
    - Example log outputs from a dry-run
        
    - Example AMU₀ snapshot (test environment)
        
    - Example governance-leak & lint reports on test content
        

You MUST NOT alter LifeOS, Alignment Layer, or the Council Protocol.  
If any step appears to require governance decisions or specification changes, stop and escalate.

---

## 10. Non-Negotiables

Throughout this work, you MUST adhere to:

- No heuristics
    
- No guessing
    
- No spontaneous reordering of steps
    
- No nondeterministic dependencies
    
- No environment drift in tests
    

If in doubt:

- Implement the safest mechanical option.
    
- Document the uncertainty clearly.
    
- Defer the decision to the CEO/Chair.
    

---

**End of Antigravity Instruction Packet — Phase 4 COO Runtime v1.0**