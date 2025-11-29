"""
Generate R6.3 Council Review Packet per Antigravity Council Review Packet Spec v1.0
"""
import os
import json
from datetime import datetime
from pathlib import Path

BUILD_ID = "72f61b7"
TIMESTAMP_UTC = "2025-11-29T05:15:00Z"

def get_all_python_files(directory):
    """Get all Python files sorted."""
    files = []
    for root, dirs, filenames in sorted(os.walk(directory)):
        dirs[:] = sorted(dirs)
        for filename in sorted(filenames):
            if filename.endswith('.py'):
                filepath = os.path.join(root, filename)
                files.append(filepath)
    return files

def generate_packet():
    output = []
    
    # 0. PACKET METADATA
    output.append("# 0. PACKET METADATA")
    output.append("")
    output.append("Phase: R6.3 — COO Runtime Breaking Changes (Linux-Only, AMU₀ Hash Changes, Subprocess Isolation)")
    output.append(f"Build_ID: {BUILD_ID}")
    output.append(f"Timestamp_UTC: {TIMESTAMP_UTC}")
    output.append("Repo_Path: coo-agent")
    output.append("")
    output.append("Spec_Versions:")
    output.append("  - LifeOS_v1.1")
    output.append("  - Alignment_Layer_v1.4")
    output.append("  - COO_Runtime_Spec_v1.0")
    output.append("  - R6.3_Fix_Packet (Final, Binding)")
    output.append("  - R6.3_Clarifications (CSO/CEO Approved)")
    output.append("")
    output.append("Scope:")
    output.append("  R6.3 Fix Packet implementation including: unified signature protocol (D2),")
    output.append("  QUESTION mapping (F3), Linux-only enforcement (B2), real hardware capture (B1),")
    output.append("  pinned subprocess isolation (B5/E2), runtime initialization (B3), time pinning")
    output.append("  verification (B4), canonical hash update (A2), AMU₀ ID derivation (A3), unified")
    output.append("  AMU₀ verification (A4), atomic rollback log writes (A6), complete subprocess")
    output.append("  migration, and signature protocol unification.")
    output.append("")
    output.append("="*80)
    output.append("")
    
    # 1. BUILD CONTEXT & AUTHORITY
    output.append("# 1. BUILD CONTEXT & AUTHORITY")
    output.append("")
    output.append("Authority Chain:")
    output.append("  This work implements the R6.3 Fix Packet (Final, Binding) with all CSO/CEO")
    output.append("  clarifications incorporated. The R6.3 Fix Packet is subordinate to LifeOS v1.1,")
    output.append("  Alignment Layer v1.4, and COO Runtime Spec v1.0. All implementation decisions")
    output.append("  follow the clarified requirements from the CSO/CEO Q&A document.")
    output.append("")
    output.append("Phase Goals (Mechanical):")
    output.append("  R6.3 introduces breaking changes to ensure fail-closed behavior, deterministic")
    output.append("  subprocess execution, real hardware capture, and proper AMU₀ integrity verification.")
    output.append("")
    output.append("  Key objectives:")
    output.append("  - Section A: AMU₀ canonical hash updates (exclude rollback log, include deep trace)")
    output.append("  - Section B: Hardware capture (real kernel/microcode), Linux-only enforcement")
    output.append("  - Section C: Rollback log integrity (atomic writes, staging verification)")
    output.append("  - Section D: Key management (env vars only, unified signatures)")
    output.append("  - Section E: Sandbox security (pinned subprocess, fixed PATH)")
    output.append("  - Section F: FSM checkpoints and QUESTION mapping")
    output.append("")
    output.append("Files Touched (Summary):")
    output.append("")
    output.append("ADDED_FILES:")
    added = [
        "coo_runtime/__init__.py",
        "coo_runtime/runtime/init.py",
        "coo_runtime/util/crypto.py",
        "coo_runtime/util/questions.py",
        "coo_runtime/util/subprocess.py"
    ]
    for f in sorted(added):
        output.append(f"  - {f}")
    output.append("")
    output.append("MODIFIED_FILES:")
    modified = [
        "coo_runtime/runtime/amu_capture.py",
        "coo_runtime/runtime/gates.py",
        "coo_runtime/runtime/migration.py",
        "coo_runtime/runtime/replay.py",
        "coo_runtime/runtime/rollback_log.py",
        "coo_runtime/util/amu0_utils.py",
        "coo_runtime/util/context.py"
    ]
    for f in sorted(modified):
        output.append(f"  - {f}")
    output.append("")
    output.append("DELETED_FILES:")
    output.append("  NONE")
    output.append("")
    output.append("="*80)
    output.append("")
    
    # 2. IMPLEMENTATION PLAN MAPPING
    output.append("# 2. IMPLEMENTATION PLAN MAPPING")
    output.append("")
    output.append("Plan Artefact References:")
    output.append("  - R6.3_Implementation_Plan.md")
    output.append("  - R6.3_Clarification_Questions.md")
    output.append("  - r6_3_clarifications.md (artifact)")
    output.append("")
    output.append("Phase-to-Code Mapping Table:")
    output.append("")
    
    mappings = [
        ("A2: Canonical Hash", "Update exclusions: rollback_log, metadata/, include external_trace", 
         ["coo_runtime/util/amu0_utils.py"]),
        ("A3: AMU₀ ID Derivation", "Hash-derived ID, no amu0_id.txt file",
         ["coo_runtime/util/amu0_utils.py", "coo_runtime/runtime/amu_capture.py"]),
        ("A4: Unified Verification", "verify_amu0_complete() with VerificationResult",
         ["coo_runtime/util/amu0_utils.py"]),
        ("A6: Atomic Rollback Log", ".tmp file pattern with atomic rename",
         ["coo_runtime/runtime/rollback_log.py"]),
        ("B1: Real Hardware Capture", "Kernel + microcode from /proc/cpuinfo",
         ["coo_runtime/util/context.py", "coo_runtime/runtime/amu_capture.py"]),
        ("B2: Linux-Only", "Platform check at import, raise ImportError",
         ["coo_runtime/__init__.py"]),
        ("B3: Runtime Init", "initialize_runtime() with hardware verification",
         ["coo_runtime/runtime/init.py"]),
        ("B4: Time Pinning", "Subprocess test with 1.1s tolerance",
         ["coo_runtime/util/context.py"]),
        ("B5/E2: Pinned Subprocess", "run_pinned_subprocess() with PATH=/usr/bin:/bin",
         ["coo_runtime/util/subprocess.py", "coo_runtime/runtime/gates.py",
          "coo_runtime/runtime/migration.py", "coo_runtime/runtime/replay.py"]),
        ("D1: Key Resolution", "get_ceo_*_key_path() from env vars only",
         ["coo_runtime/util/crypto.py"]),
        ("D2: Unified Signatures", "Signature class with 4 static methods",
         ["coo_runtime/util/crypto.py", "coo_runtime/runtime/amu_capture.py",
          "coo_runtime/runtime/rollback_log.py"]),
        ("F3: QUESTION Mapping", "QuestionType enum + raise_question()",
         ["coo_runtime/util/questions.py"])
    ]
    
    for plan_section, description, files in mappings:
        output.append(f"  Plan_Section: {plan_section}")
        output.append(f"    Description: {description}")
        output.append(f"    Key_Files: {', '.join(files)}")
        output.append("")
    
    output.append("="*80)
    output.append("")
    
    # 3. STRUCTURAL WALKTHROUGH
    output.append("# 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE)")
    output.append("")
    output.append("High-Level Architecture Changes:")
    output.append("")
    output.append("1. Foundation Layer (Phase 1)")
    output.append("   - coo_runtime/util/crypto.py: Unified Signature class")
    output.append("   - coo_runtime/util/questions.py: QUESTION type mapping")
    output.append("   - coo_runtime/util/amu0_utils.py: VerificationResult dataclass")
    output.append("")
    output.append("2. Hardware & Context Layer (Phase 2)")
    output.append("   - coo_runtime/__init__.py: Linux-only import guard")
    output.append("   - coo_runtime/util/context.py: Real hardware capture functions")
    output.append("   - coo_runtime/util/subprocess.py: Pinned subprocess helper")
    output.append("   - coo_runtime/runtime/init.py: Runtime initialization")
    output.append("")
    output.append("3. AMU₀ Integrity Layer (Phase 3)")
    output.append("   - coo_runtime/util/amu0_utils.py: calculate_canonical_hash() update")
    output.append("   - coo_runtime/util/amu0_utils.py: derive_amu0_id()")
    output.append("   - coo_runtime/util/amu0_utils.py: verify_amu0_complete()")
    output.append("   - coo_runtime/runtime/rollback_log.py: Atomic write pattern")
    output.append("")
    output.append("4. Integration Layer (Phase 4)")
    output.append("   - All subprocess calls migrated to run_pinned_subprocess()")
    output.append("   - All signing migrated to Signature class")
    output.append("   - amu_capture.py: Complete R6.3 integration")
    output.append("   - gates.py: Subprocess migration (Gates C, D)")
    output.append("   - migration.py: Subprocess migration")
    output.append("   - replay.py: Subprocess migration")
    output.append("")
    output.append("Key Behavioral Changes:")
    output.append("  - Windows: Import of coo_runtime raises ImportError immediately")
    output.append("  - AMU₀ ID: Always derived from hash, never read from file")
    output.append("  - Subprocess: All calls enforce PATH=/usr/bin:/bin")
    output.append("  - Hardware: Real kernel_version and cpu_microcode captured")
    output.append("  - Verification: Single verify_amu0_complete() replaces local checks")
    output.append("")
    output.append("="*80)
    output.append("")
    
    # 4. TESTS, GATES & DETERMINISM SURFACE
    output.append("# 4. TESTS, GATES & DETERMINISM SURFACE")
    output.append("")
    output.append("Test Status:")
    output.append("  NOT RUN - Implementation complete but requires Linux environment")
    output.append("")
    output.append("Reason:")
    output.append("  R6.3 B2 enforces sys.platform == 'linux'. Current development platform is Windows.")
    output.append("  All tests require Linux (WSL2, VM, or native) to execute.")
    output.append("")
    output.append("Test Files (Ready for Linux Execution):")
    output.append("  - coo_runtime/tests/test_r6_integration_determinism.py")
    output.append("  - coo_runtime/tests/e2e_proof_of_life.py")
    output.append("")
    output.append("Gates Affected by R6.3:")
    output.append("  - Gate C: Test Suite Integrity")
    output.append("    Change: Uses run_pinned_subprocess() for test runner")
    output.append("  - Gate D: Sandbox Security")
    output.append("    Change: Uses run_pinned_subprocess() for docker/podman inspect")
    output.append("  - Gate F: Deterministic Replay")
    output.append("    Change: Uses run_pinned_subprocess() for replay harness")
    output.append("")
    output.append("Determinism Notes:")
    output.append("  - All subprocess calls now use fixed PATH=/usr/bin:/bin")
    output.append("  - Hardware context captured once at AMU₀ creation")
    output.append("  - Canonical hash normalized with mtime=315532800")
    output.append("  - Sorted traversal for all directory operations")
    output.append("  - Rollback log uses atomic writes (prevents partial state)")
    output.append("")
    output.append("="*80)
    output.append("")
    
    # 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS
    output.append("# 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS")
    output.append("")
    output.append("AMU₀ Structure Changes:")
    output.append("")
    output.append("  Removed:")
    output.append("    - amu0_id.txt (R6.3 A3: ID now derived from hash)")
    output.append("")
    output.append("  Modified Capture (amu_capture.py):")
    output.append("    - pinned_context.json: kernel_version uses platform.release()")
    output.append("    - pinned_context.json: cpu_microcode from /proc/cpuinfo")
    output.append("    - active_amu0_path.json: includes 'mode' field (dev/prod)")
    output.append("")
    output.append("  Canonical Hash Exclusions (A2):")
    output.append("    - rollback_log.jsonl")
    output.append("    - rollback_log.sig")
    output.append("    - signature.sig")
    output.append("    - metadata/ directory")
    output.append("    - *.tmp files")
    output.append("")
    output.append("  Canonical Hash Inclusions:")
    output.append("    - external_trace.jsonl (canonical deep replay trace)")
    output.append("    - All other files in AMU₀ directory")
    output.append("")
    output.append("Sandbox Integration:")
    output.append("  - Gate D uses run_pinned_subprocess() for OCI runtime queries")
    output.append("  - Sandbox execution via pinned environment (PATH fixed)")
    output.append("")
    output.append("Freeze Mechanism:")
    output.append("  - Pinned context frozen at AMU₀ capture")
    output.append("  - Hardware verification at initialize_runtime()")
    output.append("  - Time pinning verified with 1.1s tolerance")
    output.append("  - All subprocesses use pinned context")
    output.append("")
    output.append("="*80)
    output.append("")
    
    # 6. FLATTENED CODEBASE
    output.append("# 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)")
    output.append("")
    output.append("This section contains all Python files in coo_runtime/ with R6.3 changes.")
    output.append("Files are listed in sorted order.")
    output.append("")
    
    # Get all Python files
    python_files = get_all_python_files("coo_runtime")
    
    output.append(f"Total Python Files: {len(python_files)}")
    output.append("")
    output.append("-"*80)
    output.append("")
    
    for filepath in python_files:
        rel_path = os.path.relpath(filepath, ".")
        output.append(f"FILE: {rel_path}")
        output.append("-"*80)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            output.append(content)
        except Exception as e:
            output.append(f"ERROR READING FILE: {e}")
        output.append("")
        output.append("-"*80)
        output.append("")
    
    # 7. OPEN QUESTIONS & IMPLEMENTER NOTES
    output.append("# 7. OPEN QUESTIONS & IMPLEMENTER NOTES")
    output.append("")
    output.append("Open Questions: NONE")
    output.append("")
    output.append("All R6.3 clarifications were received from CSO/CEO prior to implementation.")
    output.append("See r6_3_clarifications.md artifact for complete Q&A.")
    output.append("")
    output.append("Implementer Notes:")
    output.append("")
    output.append("1. Testing Status:")
    output.append("   R6.3 implementation is complete but untested due to Linux-only requirement.")
    output.append("   E2E and integration tests cannot run on Windows development environment.")
    output.append("   Testing requires:")
    output.append("     - Linux environment (WSL2, VM, or native)")
    output.append("     - CEO_PRIVATE_KEY_PATH and CEO_PUBLIC_KEY_PATH environment variables")
    output.append("     - Fresh AMU₀ capture on Linux")
    output.append("")
    output.append("2. Breaking Changes:")
    output.append("   - All R6.2 AMU₀s are incompatible (different hash calculation)")
    output.append("   - Windows development blocked (import raises ImportError)")
    output.append("   - Fresh AMU₀ capture required after deployment")
    output.append("")
    output.append("3. Migration Path:")
    output.append("   R6.3 explicitly does NOT support R6.2 AMU₀s. Clean break strategy confirmed")
    output.append("   by CSO/CEO clarifications. No backward compatibility layer implemented.")
    output.append("")
    output.append("4. Next Steps:")
    output.append("   - Set up Linux test environment")
    output.append("   - Generate CEO keypair for testing")
    output.append("   - Capture fresh AMU₀ on Linux")
    output.append("   - Run E2E + integration tests")
    output.append("   - Verify all gates pass")
    output.append("   - Test rollback with new log format")
    output.append("")
    output.append("="*80)
    output.append("")
    output.append("END OF COUNCIL REVIEW PACKET")
    
    return "\\n".join(output)

if __name__ == "__main__":
    print("Generating R6.3 Council Review Packet...")
    packet = generate_packet()
    
    # Ensure directory exists
    os.makedirs("council_review", exist_ok=True)
    
    # Write packet
    output_file = f"council_review/COO_Runtime_R6.3_Build_{BUILD_ID}_ReviewPacket_v1.0.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(packet)
    
    print(f"✅ Generated: {output_file}")
    print(f"   Size: {len(packet)} bytes")
    print(f"   Lines: {packet.count(chr(10)) + 1}")
