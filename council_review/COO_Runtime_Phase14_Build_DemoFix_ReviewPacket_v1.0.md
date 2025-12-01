# 0. PACKET METADATA

Phase: Phase 14 — Demo Summariser Fix (V1.1 Stage B)
Build_ID: manual_2025-12-01_v1.1_stage_b_demofix_v1.0
Timestamp_UTC: 2025-12-01T11:45:00Z
Repo_Path: coo-agent
Spec_Versions:
  - LifeOS_v1.1
  - Alignment_Layer_v1.4
  - COO_Runtime_Spec_v1.0
  - Implementation_Packet_v1.0
  - Antigravity_Instruction_Packet_Phase4_v1.0
  - COO_Runtime_V1.1_StageB_FixPack_v1.0
Scope: Application of Demo Summariser Fix (Phase 14) to V1.1 Stage B implementation.

# 1. BUILD CONTEXT & AUTHORITY

Authority Chain:
LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0 → Antigravity Instruction Packet (Phase 4) → V1.1 User Surface Spec → Fix Pack v1.0 → this Review Packet Spec.

Phase Goals (Mechanical):
Fix the `run-demo` command to ensure successful, deterministic execution of the summarisation demo by removing unsupported parameters (`top_p`, `max_tokens`) and aligning the runtime with the V1.1 specification.

Files Touched (Summary Table):

ADDED_FILES:
- NONE

MODIFIED_FILES:
- coo/cli.py
- coo/orchestrator.py
- reference/demo_mission.json
- tests/product/test_demo_receipt_format.py
- tests/product/test_demo_repeatability.py
- tests/product/test_mission_view.py
- tests/product/test_logs_view.py
- tests/product/conftest.py

DELETED_FILES:
- NONE

# 2. IMPLEMENTATION PLAN MAPPING

Plan Artefact References:
- council_review/COO Runtime V1.1 Stage B — Fix Pack.md

Phase-to-Code Mapping Table:

| Plan_Section | Brief_Mechanical_Description | Key_Files_Implemented |
| :--- | :--- | :--- |
| 3.1 Fix Model Call | Removed `top_p` and `max_tokens` from `Orchestrator` and `demo_mission.json`. | coo/orchestrator.py, reference/demo_mission.json |
| 3.2 Fixed Demo Content | Implemented fixed source text and prompt in `Orchestrator`. | coo/orchestrator.py |
| 3.3 Receipt Rendering | Updated CLI to display "Input" and "Summary (AI Output)" blocks. | coo/cli.py |
| 3.5 Align Timeline | Aligned events: `INIT` -> `MODEL_REQUEST` -> `MODEL_RESPONSE` -> `COMPLETE`. | coo/orchestrator.py, coo/cli.py |
| Verification | Updated product tests to support UUIDs and new receipt format. | tests/product/*.py |

# 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE, DESCRIPTIVE ONLY)

Module_Path: coo/orchestrator.py
Role: Runtime Orchestrator
Key_Public_Interfaces: [_run_demo_mission]
Notes: Hardcoded `DEMO_SUMMARY_SOURCE_TEXT` and `DEMO_SUMMARY_PROMPT` for determinism. Removed `top_p` and `max_tokens` from `ModelClient.chat` call. Logs full summary in `MODEL_RESPONSE`.

Module_Path: coo/cli.py
Role: CLI Entrypoint
Key_Public_Interfaces: [run_demo]
Notes: Updated receipt generation to fetch full summary from `MODEL_RESPONSE` event. Reverted ID formatting to use raw UUIDs.

Module_Path: tests/product/*.py
Role: Product Tests
Key_Public_Interfaces: [test_demo_repeatability, test_demo_receipt_format, etc.]
Notes: Updated regex to match UUIDs. Updated assertions to check for "Input" and "Summary (AI Output)" blocks.

# 4. TESTS, GATES & DETERMINISM SURFACE

Tests Overview:

Test_File: tests/product/test_demo_repeatability.py
Test_Cases: [test_demo_repeatability]
Result: PASS

Test_File: tests/product/test_demo_receipt_format.py
Test_Cases: [test_demo_receipt_format]
Result: PASS

Test_File: tests/product/test_mission_view.py
Test_Cases: [test_mission_view]
Result: PASS

Test_File: tests/product/test_logs_view.py
Test_Cases: [test_logs_view]
Result: PASS

Test_File: tests/product/test_demo_error_paths.py
Test_Cases: [test_demo_error_paths]
Result: PASS

Gates Touched:
NONE

Determinism Surface Notes:
- `Orchestrator._run_demo_mission` uses fixed input/prompt and `temperature=0`.
- `top_p` removed to avoid runtime errors and potential non-determinism (though `temperature=0` usually overrides).
- `tests/product/conftest.py` mocks `ModelClient` to ensure test determinism.

# 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS

This Phase did not modify sandbox, freeze, or AMU₀ logic.

# 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)

===== FILE START: coo/cli.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/coo/cli.py)
===== FILE END: coo/cli.py =====

===== FILE START: coo/orchestrator.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/coo/orchestrator.py)
===== FILE END: coo/orchestrator.py =====

===== FILE START: reference/demo_mission.json =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/reference/demo_mission.json)
===== FILE END: reference/demo_mission.json =====

===== FILE START: tests/product/test_demo_receipt_format.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/product/test_demo_receipt_format.py)
===== FILE END: tests/product/test_demo_receipt_format.py =====

===== FILE START: tests/product/test_demo_repeatability.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/product/test_demo_repeatability.py)
===== FILE END: tests/product/test_demo_repeatability.py =====

===== FILE START: tests/product/test_mission_view.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/product/test_mission_view.py)
===== FILE END: tests/product/test_mission_view.py =====

===== FILE START: tests/product/test_logs_view.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/product/test_logs_view.py)
===== FILE END: tests/product/test_logs_view.py =====

===== FILE START: tests/product/conftest.py =====
render_diffs(file:///c:/Users/cabra/Projects/COOProject/coo-agent/tests/product/conftest.py)
===== FILE END: tests/product/conftest.py =====

# 7. VERIFICATION LOGS

## Product Tests
```
C:\Users\cabra\AppData\Roaming\Python\Python312\site-packages\pytest
PASSED [ 20%] tests/product/test_demo_error_paths.py::test_demo_error_paths
PASSED [ 40%] tests/product/test_demo_receipt_format.py::test_demo_receipt_format
PASSED [ 60%] tests/product/test_demo_repeatability.py::test_demo_repeatability
PASSED [ 80%] tests/product/test_logs_view.py::test_logs_view
PASSED [100%] tests/product/test_mission_view.py::test_mission_view
Exit code: 0
```

## Manual Verification
```
[coo] Running deterministic demo mission ...

Mission
  ID: 1e247d0c-19c6-44fd-883d-57cba1d64c10
  Type: DEMO_V1_1
  Status: SUCCESS
  Started: 2025-12-01 11:35:19
  Finished: 2025-12-01 11:35:24
  Steps: 4 transitions, 0 rollbacks, 0 divergences

Input
  This demo shows how the COO Runtime runs a deterministic LLM call.
  The runtime takes a fixed text and produces a short summary.

Summary (AI Output)
  The Agentic Compute Engine (ACE) is a secure, deterministic runtime for autonomous agents, leveraging a cryptographic Mission Log to track state transitions and ensure replayability. It separates reasoning from execution to prevent corruption and enforces capability-based security for network and filesystem writes, governed by a deterministic policy engine.

Determinism
  This result is reproducible on this machine.
  Re-running 'coo run-demo' with the same setup will produce the same output.
  The runtime captured a sealed internal snapshot and log for this run.

Inspect
  coo mission 1e247d0c-19c6-44fd-883d-57cba1d64c10
  coo logs 1e247d0c-19c6-44fd-883d-57cba1d64c10
```
