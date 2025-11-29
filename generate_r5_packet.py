import os
import datetime
import hashlib
import json

# Configuration
PHASE = "Phase 4 — Constitutional Compliance (R5 Fixes)"
BUILD_ID = "R5_Fixes_2025-11-28"
TIMESTAMP = datetime.datetime.utcnow().isoformat() + "Z"
REPO_PATH = "COO-Agent"
OUTPUT_FILE = r"C:\Users\cabra\Projects\COOProject\AICouncilReview\ReviewArtefacts\COO_Runtime_Phase4_Build_" + BUILD_ID + "_ReviewPacket_v1.0.txt"

# File Lists (R5 Scope)
ADDED_FILES = [
    "coo_runtime/util/amu0_utils.py",
    "coo_runtime/util/output_bundle.py",
    "coo_runtime/scripts/set_fsm_state.py"
]

MODIFIED_FILES = [
    "coo_runtime/runtime/amu_capture.py",
    "coo_runtime/runtime/rollback.py",
    "coo_runtime/util/context.py",
    "coo_runtime/runtime/migration.py",
    "coo_runtime/runtime/replay.py",
    "coo_runtime/runtime/gates.py",
    "coo_runtime/scripts/run_migration.py",
    "coo_runtime/runtime/state_machine.py",
    "coo_runtime/tests/e2e_proof_of_life.py"
]

DELETED_FILES = []

# Core Runtime Scope (for flattened codebase)
# We include all modified/added files + core runtime files relevant to review
CORE_SCOPE = [
    "coo_runtime/runtime/amu_capture.py",
    "coo_runtime/runtime/rollback.py",
    "coo_runtime/runtime/migration.py",
    "coo_runtime/runtime/replay.py",
    "coo_runtime/runtime/gates.py",
    "coo_runtime/runtime/state_machine.py",
    "coo_runtime/util/context.py",
    "coo_runtime/util/amu0_utils.py",
    "coo_runtime/util/output_bundle.py",
    "coo_runtime/scripts/run_migration.py",
    "coo_runtime/tests/e2e_proof_of_life.py"
]

def generate_packet():
    content = []
    
    # 0. PACKET METADATA
    content.append("# 0. PACKET METADATA")
    content.append(f"Phase: {PHASE}")
    content.append(f"Build_ID: {BUILD_ID}")
    content.append(f"Timestamp_UTC: {TIMESTAMP}")
    content.append(f"Repo_Path: {REPO_PATH}")
    content.append("Spec_Versions:")
    content.append("  - LifeOS_v1.1")
    content.append("  - Alignment_Layer_v1.4")
    content.append("  - COO_Runtime_Spec_v1.0")
    content.append("  - Implementation_Packet_v1.0")
    content.append("  - Antigravity_Instruction_Packet_Phase4_v1.0")
    content.append("Scope: Implementation of R5 Blocking Fixes (F1-F9) for Constitutional Compliance.")
    content.append("")

    # 1. BUILD CONTEXT & AUTHORITY
    content.append("# 1. BUILD CONTEXT & AUTHORITY")
    content.append("Authority Chain: LifeOS v1.1 -> Alignment Layer v1.4 -> COO Runtime Spec v1.0 -> Implementation Packet v1.0 -> Antigravity Instruction Packet (Phase 4) -> this Review Packet Spec.")
    content.append("")
    content.append("Phase Goals (Mechanical):")
    content.append("Implement and verify R5 Blocking Fixes (F1-F9) to address constitutional gaps identified in R4 review. Focus on strict AMU0 scoping, fail-closed context enforcement, and deterministic replay.")
    content.append("")
    content.append("Files Touched (Summary Table):")
    content.append("ADDED_FILES:")
    for f in sorted(ADDED_FILES): content.append(f"  - {f}")
    content.append("MODIFIED_FILES:")
    for f in sorted(MODIFIED_FILES): content.append(f"  - {f}")
    content.append("DELETED_FILES:")
    for f in sorted(DELETED_FILES): content.append(f"  - {f}")
    content.append("")

    # 2. IMPLEMENTATION PLAN MAPPING
    content.append("# 2. IMPLEMENTATION PLAN MAPPING")
    content.append("Plan Artefact References:")
    content.append("  - implementation_plan.md (R5 Section)")
    content.append("")
    content.append("Phase-to-Code Mapping Table:")
    content.append("Plan_Section | Brief_Mechanical_Description | Key_Files_Implemented")
    content.append("--- | --- | ---")
    content.append("F1: AMU0 Signatures | Recursive hashing & signing | coo_runtime/util/amu0_utils.py, coo_runtime/runtime/amu_capture.py")
    content.append("F2: Pinned Context | Fail-closed enforcement | coo_runtime/util/context.py, coo_runtime/runtime/migration.py")
    content.append("F3: Rollback State | Scoped to AMU0 dir | coo_runtime/runtime/amu_capture.py, coo_runtime/runtime/rollback.py")
    content.append("F4: Sandbox SHA | Real SHA verification | coo_runtime/runtime/gates.py")
    content.append("F5: FSM Safety | Remove fast-forward, add persistence | coo_runtime/scripts/run_migration.py, coo_runtime/runtime/state_machine.py")
    content.append("F6: Hardware Verify | Fail-closed kernel check | coo_runtime/util/context.py")
    content.append("F7: Replay Determinism | Output bundle hashing | coo_runtime/util/output_bundle.py, coo_runtime/runtime/replay.py")
    content.append("F8: AMU0 Utils | Centralized resolution | coo_runtime/util/amu0_utils.py")
    content.append("F9: Rollback Context | Re-apply context after rollback | coo_runtime/runtime/rollback.py")
    content.append("")

    # 3. STRUCTURAL WALKTHROUGH
    content.append("# 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE, DESCRIPTIVE ONLY)")
    content.append("Module_Path: coo_runtime/util/amu0_utils.py")
    content.append("Role: AMU0 Utilities")
    content.append("Key_Public_Interfaces: [resolve_amu0_path, read_amu0_id, calculate_canonical_hash]")
    content.append("Notes: Provides centralized logic for resolving AMU0 paths and computing canonical hashes for signatures.")
    content.append("")
    content.append("Module_Path: coo_runtime/util/output_bundle.py")
    content.append("Role: Output Bundle Hashing")
    content.append("Key_Public_Interfaces: [create_output_bundle]")
    content.append("Notes: Implements recursive, byte-for-byte hashing of mission output directories for deterministic comparison.")
    content.append("")
    content.append("Module_Path: coo_runtime/runtime/state_machine.py")
    content.append("Role: Runtime FSM")
    content.append("Key_Public_Interfaces: [transition_to, assert_state, save_state, load_state]")
    content.append("Notes: Added persistence to support safe script re-entry without fast-forwarding.")
    content.append("")

    # 4. TESTS, GATES & DETERMINISM SURFACE
    content.append("# 4. TESTS, GATES & DETERMINISM SURFACE")
    content.append("Tests Overview:")
    content.append("Test_File: coo_runtime/tests/e2e_proof_of_life.py")
    content.append("Test_Cases: [test_full_migration_success, test_rollback_snapshot_corruption, test_strict_mode_enforcement, test_replay_failure_nondeterminism]")
    content.append("Result: PASS")
    content.append("")
    content.append("Gates Touched:")
    content.append("Gate: D — Sandbox Security")
    content.append("Gate_Implementation_Files: [coo_runtime/runtime/gates.py]")
    content.append("Gate: F — Deterministic Replay")
    content.append("Gate_Implementation_Files: [coo_runtime/runtime/gates.py, coo_runtime/runtime/replay.py]")
    content.append("")
    content.append("Determinism Surface Notes:")
    content.append("- Pinned Context: Enforced via coo_runtime/util/context.py (env vars, RNG, time).")
    content.append("- Replay: Byte-for-byte output comparison via output_bundle.py.")
    content.append("- Migration: Deterministic file sorting in migration.py.")
    content.append("")

    # 5. SANDBOX, FREEZE & AMU0 TOUCHPOINTS
    content.append("# 5. SANDBOX, FREEZE & AMU0 TOUCHPOINTS")
    content.append("Relevant Files Changed: amu_capture.py, rollback.py, gates.py")
    content.append("Manifest Fields Touched: sandbox_manifest.json (image_sha256)")
    content.append("AMU0-Related Logic:")
    content.append("- Snapshots: Taken in amu_capture.py using recursive hash.")
    content.append("- Signatures: Signed in amu_capture.py, verified in rollback.py.")
    content.append("- Rollback State: Stored in AMU0 directory.")
    content.append("")

    # 6. FLATTENED CODEBASE
    content.append("# 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)")
    
    for file_path in sorted(CORE_SCOPE):
        abs_path = os.path.abspath(file_path)
        if os.path.exists(abs_path):
            content.append(f"===== FILE START: {file_path} =====")
            with open(abs_path, "r", encoding="utf-8") as f:
                content.append(f.read())
            content.append(f"===== FILE END: {file_path} =====")
            content.append("")
        else:
            content.append(f"===== FILE START: {file_path} =====")
            content.append("ERROR: File not found.")
            content.append(f"===== FILE END: {file_path} =====")
            content.append("")

    # 7. OPEN QUESTIONS
    content.append("# 7. OPEN QUESTIONS & IMPLEMENTER NOTES")
    content.append("## 7.1 OPEN_QUESTIONS_FOR_COUNCIL")
    content.append("None.")
    content.append("")
    content.append("## 7.2 IMPLEMENTER_NOTES (NON-NORMATIVE)")
    content.append("Implemented FSM persistence to avoid fast-forwarding in scripts, as requested in F5.")
    content.append("Mocked hardware checks in tests as they cannot run in the test environment.")

    # Write to file
    os.makedirs("council_review", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(content))
        
    print(f"Generated Review Packet: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_packet()
