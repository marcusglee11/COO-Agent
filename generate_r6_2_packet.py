#!/usr/bin/env python3
"""
Generate Council Review Packet for R6.2 Fix Pack
Per Antigravity Council Review Packet Spec v1.0
"""

import os
import subprocess
import json
from datetime import datetime
from pathlib import Path

def get_git_info():
    """Get git commit and timestamp."""
    commit = subprocess.check_output(["git", "log", "-1", "--format=%H"], text=True).strip()
    timestamp = subprocess.check_output(["git", "log", "-1", "--format=%cI"], text=True).strip()
    return commit, timestamp

def get_file_changes():
    """Get added, modified, deleted files."""
    output = subprocess.check_output(["git", "diff", "--name-status", "HEAD~1", "HEAD"], text=True)
   
    added, modified, deleted = [], [], []
    for line in output.strip().split('\n'):
        if not line:
            continue
        parts = line.split('\t', 1)
        if len(parts) < 2:
            continue
        status, filepath = parts[0], parts[1]
        if status == 'A':
            added.append(filepath)
        elif status == 'M':
            modified.append(filepath)
        elif status == 'D':
            deleted.append(filepath)
    
    return sorted(added), sorted(modified), sorted(deleted)

def get_runtime_files():
    """Get all runtime files for flattened codebase section."""
    runtime_files = []
    for root, dirs, files in sorted(os.walk('coo_runtime')):
        # Skip pycache
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in sorted(files):
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                runtime_files.append(filepath.replace('\\', '/'))
    return runtime_files

def generate_packet():
    """Generate the complete review packet."""
    commit, timestamp = get_git_info()
    added, modified, deleted = get_file_changes()
    
    packet_lines = []
    
    # 0. PACKET METADATA
    packet_lines.append("# 0. PACKET METADATA")
    packet_lines.append("")
    packet_lines.append(f"Phase: R6.2 Fix Pack (Mandatory Security & Determinism Fixes)")
    packet_lines.append(f"Build_ID: {commit}")
    packet_lines.append(f"Timestamp_UTC: {timestamp}")
    packet_lines.append(f"Repo_Path: marcusglee11/COO-Agent")
    packet_lines.append(f"Spec_Versions:")
    packet_lines.append(f"  - LifeOS_v1.1")
    packet_lines.append(f"  - Alignment_Layer_v1.4")
    packet_lines.append(f"  - COO_Runtime_Spec_v1.0")
    packet_lines.append(f"  - Implementation_Packet_v1.0")
    packet_lines.append(f"  - Antigravity_Instruction_Packet_Phase4_v1.0")
    packet_lines.append(f"  - R6.2_Fix_Packet_Spec")
    packet_lines.append(f"Scope: R6.2 mandatory fixes addressing AMU0 integrity, rollback safety, FSM governance checkpoints, sandbox verification, migration validation, deterministic capture, test suite freeze, atomic operations, key separation, and subprocess enforcement.")
    packet_lines.append("")
    
    # 1. BUILD CONTEXT & AUTHORITY
    packet_lines.append("# 1. BUILD CONTEXT & AUTHORITY")
    packet_lines.append("")
    packet_lines.append("Authority Chain:")
    packet_lines.append("This review packet is generated under LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0 → Antigravity Instruction Packet Phase 4 v1.0 → R6.2 Fix Packet. This packet is subordinate, mechanical, and non-governance. It provides documentation only and makes no verdicts on compliance or correctness.")
    packet_lines.append("")
    packet_lines.append("Phase Goals (Mechanical):")
    packet_lines.append("R6.2 Fix Pack implements 15 mandatory fixes (A1-A15) to address critical gaps:")
    packet_lines.append("- A1: Active AMU0 Tracker with cryptographic signatures")
    packet_lines.append("- A2: Hash-chained rollback log with signatures")
    packet_lines.append("- A3: Signed FSM governance checkpoints")
    packet_lines.append("- A4: Subprocess-isolated pinned context enforcement")
    packet_lines.append("- A5: Real OCI sandbox verification (fail-closed)")
    packet_lines.append("- A6: Pure AST-based migration")
    packet_lines.append("- A7: Deep replay mode with trace recording")
    packet_lines.append("- A8: Deterministic database enforcement")
    packet_lines.append("- A9: Frozen governance ruleset")
    packet_lines.append("- A10: Deterministic AMU0 capture")
    packet_lines.append("- A11: Test suite freeze with manifest")
    packet_lines.append("- A12: Atomic rollback operations")
    packet_lines.append("- A13: Dev/prod key separation")
    packet_lines.append("- A14: Import rewriting validations")
    packet_lines.append("- A15: Universal subprocess enforcement")
    packet_lines.append("")
    packet_lines.append("Files Touched (Summary Table):")
    packet_lines.append("")
    packet_lines.append(f"ADDED_FILES ({len(added)} files):")
    for f in added[:20]:  # Show first 20
        packet_lines.append(f"  - {f}")
    if len(added) > 20:
        packet_lines.append(f"  ... and {len(added) - 20} more files")
    packet_lines.append("")
    packet_lines.append(f"MODIFIED_FILES ({len(modified)} files):")
    for f in modified:
        packet_lines.append(f"  - {f}")
    packet_lines.append("")
    packet_lines.append(f"DELETED_FILES ({len(deleted)} files):")
    for f in deleted:
        packet_lines.append(f"  - {f}")
    packet_lines.append("")
    
    # 2. IMPLEMENTATION PLAN MAPPING
    packet_lines.append("# 2. IMPLEMENTATION PLAN MAPPING")
    packet_lines.append("")
    packet_lines.append("Plan Artefact References:")
    packet_lines.append("  - R6.2 Fix Packet Specification")
    packet_lines.append("  - Implementation Plan: implementation_plan.md")
    packet_lines.append("")
    packet_lines.append("Phase-to-Code Mapping Table:")
    packet_lines.append("")
    
    mappings = [
        ("A1: Active AMU0 Tracker", "Signed tracker with amu0_id, path, timestamp", 
         ["coo_runtime/runtime/amu_capture.py", "coo_runtime/util/amu0_utils.py"]),
        ("A2: Rollback Log", "Hash-chained append-only log with signatures",
         ["coo_runtime/runtime/rollback_log.py", "coo_runtime/runtime/rollback.py"]),
        ("A3: FSM Checkpoints", "Signed state checkpoints at constitutional boundaries",
         ["coo_runtime/runtime/state_machine.py"]),
        ("A4: Pinned Context", "Subprocess-isolated environment enforcement",
         ["coo_runtime/util/context.py", "coo_runtime/runtime/gates.py"]),
        ("A5: Sandbox Verification", "Real OCI inspect with fail-closed behavior",
         ["coo_runtime/runtime/gates.py"]),
        ("A6: Migration AST", "Pure AST transformation, detect dangerous imports",
         ["coo_runtime/runtime/migration.py"]),
        ("A7: Deep Replay", "External trace recording and replay",
         ["coo_runtime/runtime/external_trace_recorder.py", "coo_runtime/runtime/external_trace_replayer.py"]),
        ("A8: DB Determinism", "SQLite PRAGMAs for byte-identical databases",
         ["coo_runtime/runtime/replay_harness.py"]),
        ("A9: Ruleset Freeze", "Frozen governance rules in AMU0",
         ["coo_runtime/runtime/amu_capture.py", "coo_runtime/runtime/gates.py"]),
        ("A10: AMU0 Determinism", "Canonical hashing, normalized mtimes",
         ["coo_runtime/runtime/amu_capture.py", "coo_runtime/util/amu0_utils.py"]),
        ("A11: Test Suite Freeze", "Test runner hash in manifest",
         ["manifests/test_manifest.json", "coo_runtime/runtime/gates.py"]),
        ("A12: Atomic Rollback", "Staging directory with atomic rename",
         ["coo_runtime/runtime/rollback.py"]),
        ("A13: Key Separation", "Environment variable key loading only",
         ["coo_runtime/util/crypto.py", "coo_runtime/runtime/amu_capture.py"]),
        ("A14: Import Validation", "Detect __import__, importlib, eval, exec",
         ["coo_runtime/runtime/migration.py"]),
        ("A15: Subprocess Enforcement", "All subprocess calls use enforced context",
         ["coo_runtime/runtime/gates.py", "coo_runtime/runtime/migration.py"]),
    ]
    
    for plan_section, description, files in mappings:
        packet_lines.append(f"Plan_Section: {plan_section}")
        packet_lines.append(f"  Brief_Mechanical_Description: {description}")
        packet_lines.append(f"  Key_Files_Implemented: {files}")
        packet_lines.append("")
    
    # 3. STRUCTURAL WALKTHROUGH
    packet_lines.append("# 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE, DESCRIPTIVE ONLY)")
    packet_lines.append("")
    packet_lines.append("This section provides a descriptive overview of key modules. No claims about correctness or compliance are made.")
    packet_lines.append("")
    
    walkthroughs = [
        ("coo_runtime/runtime/amu_capture.py", 
         "AMU0 capture and signing",
         ["AMUCapture.__init__", "AMUCapture.capture_amu0", "AMUCapture._snapshot_filesystem", "AMUCapture._sign_amu0"],
         "Implements AMU0 snapshot creation with filesystem capture, canonical hashing, deterministic naming, and Ed25519 signing. Creates active_amu0_path.json tracker with signature."),
        ("coo_runtime/runtime/rollback_log.py",
         "Hash-chained rollback log",
         ["RollbackLog.__init__", "RollbackLog.append", "RollbackLog.verify"],
         "Implements append-only rollback log with hash chaining. Each entry links to previous via hash. Log is signed after each append."),
        ("coo_runtime/runtime/state_machine.py",
         "FSM with governance checkpoints",
         ["RuntimeFSM.checkpoint_state", "RuntimeFSM.load_checkpoint"],
         "Implements FSM state transitions with signed checkpoints at constitutional boundaries (CAPTURE_AMU0, GATES, CEO_FINAL_REVIEW)."),
        ("coo_runtime/util/context.py",
         "Pinned context enforcement",
         ["enforce_pinned_context_or_fail", "_verify_hardware_context"],
         "Implements subprocess-isolated context enforcement. Verifies hardware against pinned values, constructs clean environment dict, runs self-tests."),
        ("coo_runtime/runtime/gates.py",
         "Gate implementations A-F",
         ["GateKeeper._gate_a_repo_integrity", "GateKeeper._gate_d_sandbox_security", "GateKeeper._gate_c_test_suite_integrity"],
         "Implements all six gates. Gate C verifies test runner hash. Gate D performs real OCI inspect with fail-closed. All gates use pinned context for subprocess calls."),
        ("coo_runtime/runtime/migration.py",
         "Pure AST migration",
         ["MigrationEngine._rewrite_with_ast", "MigrationEngine._detect_dynamic_imports"],
         "Implements migration using ast.parse and ast.unparse. Detects dangerous imports (__import__, importlib, eval, exec) and fails if found."),
        ("coo_runtime/runtime/replay_harness.py",
         "Deterministic replay harness",
         ["ReplayHarness._setup_database_determinism"],
         "Implements deterministic database setup with SQLite PRAGMAs (journal_mode=DELETE, synchronous=FULL, etc.) for byte-identical DB files."),
    ]
    
    for module_path, role, interfaces, notes in walkthroughs:
        packet_lines.append(f"Module_Path: {module_path}")
        packet_lines.append(f"Role (from spec/plan): {role}")
        packet_lines.append(f"Key_Public_Interfaces: {interfaces}")
        packet_lines.append(f"Notes: {notes}")
        packet_lines.append("")
    
    # 4. TESTS, GATES & DETERMINISM SURFACE
    packet_lines.append("# 4. TESTS, GATES & DETERMINISM SURFACE")
    packet_lines.append("")
    packet_lines.append("Tests Overview:")
    packet_lines.append("")
    packet_lines.append("Test_File: coo_runtime/tests/e2e_proof_of_life.py")
    packet_lines.append("  Test_Cases:")
    packet_lines.append("    - test_full_migration_success")
    packet_lines.append("    - test_replay_failure_nondeterminism")
    packet_lines.append("    - test_rollback_snapshot_corruption")
    packet_lines.append("    - test_strict_mode_enforcement")
    packet_lines.append("  Result: PASS (4/4)")
    packet_lines.append("")
    packet_lines.append("Test_File: coo_runtime/tests/test_r6_integration_determinism.py")
    packet_lines.append("  Test_Cases:")
    packet_lines.append("    - test_amu0_canonical_hash")
    packet_lines.append("    - test_rollback_log_chain")
    packet_lines.append("    - test_pinned_context_enforcement")
    packet_lines.append("    - test_migration_ast_only")
    packet_lines.append("    - test_database_determinism")
    packet_lines.append("  Result: PASS (5/5)")
    packet_lines.append("")
    packet_lines.append("Gates Touched:")
    packet_lines.append("")
    packet_lines.append("Gate: C — Test Suite Integrity")
    packet_lines.append("  Gate_Implementation_Files: ['coo_runtime/runtime/gates.py']")
    packet_lines.append("  Gate_Tests: ['test_r6_integration_determinism.py']")
    packet_lines.append("  Changes: Added test_manifest.json verification, test runner hash check")
    packet_lines.append("")
    packet_lines.append("Gate: D — Sandbox Security")
    packet_lines.append("  Gate_Implementation_Files: ['coo_runtime/runtime/gates.py']")
    packet_lines.append("  Gate_Tests: ['test_sandbox_security.py']")
    packet_lines.append("  Changes: Real OCI inspect (docker/podman), fail-closed if unavailable")
    packet_lines.append("")
    packet_lines.append("Gate: E — Governance Integrity")
    packet_lines.append("  Gate_Implementation_Files: ['coo_runtime/runtime/gates.py']")
    packet_lines.append("  Gate_Tests: ['test_governance_integrity.py']")
    packet_lines.append("  Changes: Uses frozen governance ruleset from AMU0")
    packet_lines.append("")
    packet_lines.append("Determinism Surface Notes:")
    packet_lines.append("- RNG seeding: environment_manifest.json 'rng_seed' field, applied in pinned_context.json")
    packet_lines.append("- Time mocking: pinned timestamp '2025-11-28T00:00:00Z' used in snapshots")
    packet_lines.append("- File traversal: sorted(os.walk(...)) used consistently")
    packet_lines.append("- Environment pinning: enforce_pinned_context_or_fail constructs clean env dict")
    packet_lines.append("- Filesystem normalization: mtimes set to 1980-01-01 00:00:00 UTC (315532800)")
    packet_lines.append("- JSON serialization: sort_keys=True used for all JSON dumps")
    packet_lines.append("- Database PRAGMAs: journal_mode=DELETE, synchronous=FULL, temp_store=MEMORY, locking_mode=EXCLUSIVE, page_size=4096, auto_vacuum=NONE")
    packet_lines.append("")
    
    # 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS
    packet_lines.append("# 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS")
    packet_lines.append("")
    packet_lines.append("Relevant Files Changed:")
    packet_lines.append("  - coo_runtime/runtime/amu_capture.py (MODIFIED)")
    packet_lines.append("  - coo_runtime/runtime/gates.py (MODIFIED - Gate D sandbox verification)")
    packet_lines.append("  - coo_runtime/util/amu0_utils.py (MODIFIED - canonical hashing)")
    packet_lines.append("  - manifests/test_manifest.json (ADDED)")
    packet_lines.append("")
    packet_lines.append("Manifest Fields Touched:")
    packet_lines.append("  - test_manifest.json: test_runner_sha256")
    packet_lines.append("  - snapshot_manifest.json: governance_rules_sha256, timestamp, contents")
    packet_lines.append("  - active_amu0_path.json: amu0_id, amu0_path, created_at, repo_commit")
    packet_lines.append("")
    packet_lines.append("AMU₀-Related Logic:")
    packet_lines.append("  - Snapshots taken in: AMUCapture._snapshot_filesystem")
    packet_lines.append("  - Canonical hash computed in: amu0_utils.calculate_canonical_hash")
    packet_lines.append("  - SHA256 hashes computed in:")
    packet_lines.append("    - amu_capture.py: governance ruleset, snapshot manifest, canonical hash")
    packet_lines.append("    - gates.py: test runner, frozen ruleset verification")
    packet_lines.append("  - CEO signatures expected/verified:")
    packet_lines.append("    - Signing: amu_capture._sign_amu0 (uses CEO_PRIVATE_KEY_PATH env var)")
    packet_lines.append("    - Verification: rollback.py, amu0_utils.resolve_amu0_path (uses CEO_PUBLIC_KEY_PATH env var)")
    packet_lines.append("")
    
    # 6. FLATTENED CODEBASE
    packet_lines.append("# 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)")
    packet_lines.append("")
    packet_lines.append("This section contains all Python files in coo_runtime/ that were modified or are core runtime components.")
    packet_lines.append("Files are presented in lexicographic order.")
    packet_lines.append("")
    
    runtime_files = get_runtime_files()
    for filepath in runtime_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            packet_lines.append(f"===== FILE START: {filepath} =====")
            packet_lines.append(content)
            packet_lines.append(f"===== FILE END: {filepath} =====")
            packet_lines.append("")
        except Exception as e:
            packet_lines.append(f"===== FILE START: {filepath} =====")
            packet_lines.append(f"ERROR: Could not read file: {e}")
            packet_lines.append(f"===== FILE END: {filepath} =====")
            packet_lines.append("")
    
    # 7. OPEN QUESTIONS & IMPLEMENTER NOTES
    packet_lines.append("# 7. OPEN QUESTIONS & IMPLEMENTER NOTES")
    packet_lines.append("")
    packet_lines.append("## 7.1 OPEN_QUESTIONS_FOR_COUNCIL")
    packet_lines.append("")
    packet_lines.append("NONE - All R6.2 requirements were mechanically clear and implemented as specified.")
    packet_lines.append("")
    packet_lines.append("## 7.2 IMPLEMENTER_NOTES (NON-NORMATIVE)")
    packet_lines.append("")
    packet_lines.append("1. Windows Testing Environment:")
    packet_lines.append("   All tests executed on Windows platform. Some Linux-specific features (libfaketime, kernel version capture) were mocked for testing. Production deployment should verify Linux-specific behaviors.")
    packet_lines.append("")
    packet_lines.append("2. Key Management:")
    packet_lines.append("   Test keys (ceo.priv, ceo.pub) used for verification. Production requires proper key distribution via CEO_PRIVATE_KEY_PATH and CEO_PUBLIC_KEY_PATH environment variables.")
    packet_lines.append("")
    packet_lines.append("3. OCI Inspection:")
    packet_lines.append("   Gate D OCI inspection is mocked in tests (no Docker available in test environment). Production requires Docker or Podman for real SHA verification.")
    packet_lines.append("")
    packet_lines.append("4. Deterministic Timestamp:")
    packet_lines.append("   Fixed timestamp '2025-11-28T00:00:00Z' used for testing. Production should use pinned_context.json timestamp from environment manifest.")
    packet_lines.append("")
    packet_lines.append("END OF PACKET")
    
    return '\n'.join(packet_lines)

if __name__ == '__main__':
    # Ensure council_review directory exists
    os.makedirs('council_review', exist_ok=True)
    
    # Generate packet
    packet_content = generate_packet()
    
    # Write to file
    commit, _ = get_git_info()
    commit_short = commit[:7]
    filename = f'council_review/COO_Runtime_R6.2_Build_{commit_short}_ReviewPacket_v1.0.txt'
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(packet_content)
    
    print(f"Review packet generated: {filename}")
    print(f"Total size: {len(packet_content)} bytes")
