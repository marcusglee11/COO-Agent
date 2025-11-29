---
description: Generate Council Review Packet per Spec v1.0
---

# Generate Council Review Packet

This workflow MUST be executed whenever a build/fix phase completes.

## When to Run

Execute this workflow when:
1. A phase build completes successfully (e.g., R6.3, Phase 4, etc.)
2. At least one file was added/modified in coo_runtime/
3. You have a build identifier (git commit SHA)

## Steps

// turbo-all

1. **Read the spec**
   ```
   Read docs/Antigravity_Council_Review_Packet_Spec_v1.0.md
   ```

2. **Get build metadata**
   ```bash
   git rev-parse HEAD  # Get commit SHA for Build_ID
   ```

3. **Generate packet script**
   Create or update `generate_r6_3_packet.py` (or similar) following the spec format:
   - Section 0: Packet Metadata
   - Section 1: Build Context & Authority
   - Section 2: Implementation Plan Mapping
   - Section 3: Structural Walkthrough
   - Section 4: Tests, Gates & Determinism Surface
   - Section 5: Sandbox, Freeze & AMU₀ Touchpoints
   - Section 6: Flattened Codebase
   - Section 7: Open Questions & Implementer Notes

4. **Run packet generator**
   ```bash
   python generate_r6_3_packet.py
   ```

5. **Verify output**
   - File: `council_review/COO_Runtime_<PHASE>_Build_<BUILD_ID>_ReviewPacket_v1.0.txt`
   - Check all 7 sections are present
   - Verify deterministic ordering (sorted paths)

6. **Commit packet**
   ```bash
   git add council_review/*.txt generate_*.py
   git commit -m "docs(<phase>): Generate Council Review Packet v1.0"
   ```

## Checklist

- [ ] Spec read and understood
- [ ] Build_ID obtained (commit SHA)
- [ ] All 7 sections included
- [ ] Flattened codebase complete
- [ ] File paths sorted
- [ ] Packet committed to repo
- [ ] Ready for Council review

## Notes

- The spec is MECHANICAL ONLY - no verdicts or approvals
- Sections must appear in exact order per spec
- Flattened codebase must include ALL relevant files
- Use deterministic traversal (sorted)
