---
description: Generate Council Review Packet per Spec v1.0
---

This workflow describes how to generate the Council Review Packet after a successful build, as per `docs/Antigravity_Council_Review_Packet_Spec_v1.0.md`.

1. **Identify Build Metadata**:
   - Phase (e.g., "Phase 4 — Constitutional Compliance")
   - Build ID (e.g., Git SHA or "R4_Fixes_YYYY-MM-DD")
   - Timestamp (UTC)
   - Scope (Brief description of changes)

2. **Identify Modified Files**:
   - List all files added, modified, or deleted in this build.
   - Also identify core runtime modules if not modified but relevant.

3. **Construct Packet Content (Sections 0-5, 7)**:
   - Follow the structure in `docs/Antigravity_Council_Review_Packet_Spec_v1.0.md`.
   - **Section 0**: Metadata.
   - **Section 1**: Build Context & Authority (Restate authority chain, goals, file list).
   - **Section 2**: Implementation Plan Mapping (Map plan sections to code).
   - **Section 3**: Structural Walkthrough (Non-normative descriptions of modules).
   - **Section 4**: Tests, Gates & Determinism (Test results, gates touched, determinism notes).
   - **Section 5**: Sandbox, Freeze & AMU0 Touchpoints (Manifests, snapshots, signatures).
   - **Section 7**: Open Questions & Notes.

4. **Write Initial Packet**:
   - Construct the text for Sections 0-5.
   - Write to `C:\Users\cabra\Projects\COOProject\AICouncilReview\ReviewArtefacts\COO_Runtime_Phase<PHASE>_Build_<BUILD_ID>_ReviewPacket_v1.0.txt`.

5. **Append Flattened Codebase (Section 6)**:
   - Append the header `# 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)` to the file (if not already in step 4).
   - Iterate through each file in the scope:
     - Append `===== FILE START: <relative_path> =====`
     - Append file content (byte-identical).
     - Append `===== FILE END: <relative_path> =====`
   - Use PowerShell to append safely:
     ```powershell
     $packet = "path/to/packet.txt"
     $files = @("file1.py", "file2.py")
     foreach ($file in $files) {
         Add-Content -Path $packet -Value "`n===== FILE START: $file =====`n" -NoNewline
         Get-Content -Path $file -Raw | Add-Content -Path $packet -NoNewline
         Add-Content -Path $packet -Value "`n===== FILE END: $file =====`n" -NoNewline
     }
     ```

6. **Append Section 7**:
   - Append Section 7 content to the end of the file.

7. **Verify**:
   - Check that the file exists and contains the expected sections and code.
