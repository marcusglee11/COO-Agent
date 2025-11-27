IMPLEMENTATION PACKET v1.0

Mechanical Execution Guide for COO Runtime v1.0
Subordinate to:

LifeOS v1.1

Alignment Layer v1.4

COO Runtime Spec v1.0
Prepared for: Antigravity

0. PURPOSE

A detailed, deterministic instruction set for Antigravity to implement the COO Runtime v1.0 and the PB→COO consolidation in a safe, reproducible, constitutional manner.

This packet covers:

Required directory structure

Required files, manifests, and metadata

Required deterministic algorithms

Required test and replay harnesses

Required environmental constraints

Required migration scripts

Required rollback scripts

Required logging formats

Required integration points with Antigravity’s build system

No governance or decision-making authority exists in this document.

1. SUBORDINATION CLAUSE
LifeOS v1.1 is supreme.  
Alignment Layer v1.4 and COO Runtime Spec v1.0 define all governance, sequencing, authority, and determinism.  
This Implementation Packet defines only mechanical behaviour.  
If any instruction conflicts with a superior document, this packet yields without exception.

2. DIRECTORY & FILE STRUCTURE

Antigravity MUST create the following directory structure:

coo_runtime/
    runtime/
        __init__.py
        state_machine.py
        amendment_engine.py
        lint_engine.py
        governance_leak_scanner.py
        freeze.py
        amu_capture.py
        migration.py
        gates.py
        replay.py
        rollback.py
        logging.py

    manifests/
        tools_manifest.json
        environment_manifest.json
        hardware_manifest.json
        sandbox_digest.txt
        freeze_manifest.json

    tests/
        test_determinism.py
        test_migration.py
        test_replay.py
        test_governance_integrity.py
        test_sandbox_security.py

    scripts/
        apply_amendments.py
        run_lint.py
        run_scanner.py
        run_tests.py
        run_replay.py
        run_migration.py
        run_rollback.py

    reference/
        phase3_reference_mission.json


No other directories are permitted unless explicitly added by future specs.

3. REQUIRED MANIFESTS

All manifests MUST be present before migration:

3.1 tools_manifest.json

Contains:

Full SHA256 of each executable

Version numbers

Build toolchain versions

3.2 environment_manifest.json

Contains:

OS version

Kernel version

Python version

Locale

PATH

Env vars relevant to runtime

3.3 hardware_manifest.json

Contains:

CPU ID

Microcode version

NUMA topology

Filesystem type

Virtualization flags

3.4 sandbox_digest.txt

SHA256 of OCI sandbox image.

3.5 freeze_manifest.json

Generated after CEO approval and Freeze activation.

4. AMENDMENT ENGINE (MECHANICAL)

Antigravity MUST implement a deterministic amendment engine:

4.1 Deterministic Anchoring

Anchor resolution MUST use:

Clause IDs

Header names

Strict whitespace normalization

UTF-8 canonical encoding

4.2 Amendment Application Algorithm

Pseudo-code:

for amendment in sorted(amendments):
    locate anchor deterministically
    if zero anchors found: raise ERROR("MissingAnchor")
    if >1 anchor found: raise ERROR("AmbiguousAnchor")
    apply replacement/insertion exactly as specified
    update amendment log

4.3 Outputs

Amended PB

Amended IP

amendment_log.json

amendment_diff.patch

5. GOVERNANCE-LEAK SCANNER

Antigravity MUST implement scanner rules exactly as defined in Alignment Layer v1.4:

Forbidden semantic patterns

Permitted patterns (CEO-only authority)

Exact-match and pattern-match rulesets

SHA256-locked ruleset

Deterministic reporting format

5.1 Output Format
{
  "status": "PASS" | "FAIL",
  "violations": [
    {
      "file": "...",
      "line": number,
      "pattern": "ForbiddenPatternName",
      "excerpt": "..."
    }
  ],
  "ruleset_sha256": "..."
}

6. CONSTITUTIONAL LINT ENGINE

Lint engine MUST validate:

Invariant compliance

Forbidden constructs

Required clauses

Missing escalation paths

Error = halt.

7. FREEZE PREPARATION

Antigravity MUST provide runtime calls to:

Halt async processes

Close file descriptors

Enforce read-only filesystem lock

Enforce DB quiescence

Compute SHA256 for tooling and sandbox

Produce freeze_manifest.json

Set FREEZE=TRUE

No mutations allowed after FREEZE=TRUE.

8. AMU₀ CAPTURE

Antigravity MUST implement deterministic snapshot tools for:

Filesystem

Database

Sandbox digest

All manifests

Hardware identity

Reference missions

All snapshots MUST be:

Byte-identical across captures

Stored in canonical sorted order

SHA256 hashed

Verified before and after capture

9. MIGRATION ENGINE

Implements the PB→COO deterministic sequence.

9.1 Canonical Porting

PB modules MUST port using:

sorted(os.walk(...))
sorted(files)

9.2 Test Harness Invocation

Must run:

First test pass pre-deletion

Second test pass post-deletion

Same test environment

Zero stochastic tests

9.3 Delete PB Directory

Deletion MUST be atomic and logged.

If ANY post-deletion test fails → rollback.

10. GATES ENGINE

Antigravity MUST implement each gate exactly:

Gate A: Repo Unification Integrity

Validate directory structure, imports, missing PB paths.

Gate B: Deterministic Modules

Hash of module outputs MUST match across repeated invocations.

Gate D: Sandbox Security

Validate sandbox digest and entrypoint.

Gate C: Test Suite Integrity

Full pass required.

Gate E: Governance Integrity

Run scanner + lint.

Gate F: Deterministic Replay

Call replay engine (Section 11).

Failure at ANY gate triggers rollback engine.

11. REPLAY ENGINE

The replay engine MUST freeze:

RNG

Time

CPU microcode

NUMA topology

Filesystem type

Kernel

PID

Env vars

Reference missions

Open FDs

Replay harness MUST:

Execute reference mission

Capture outputs

Re-execute

Byte-compare

Outputs MUST be identical.

12. ROLLBACK ENGINE

Rollback MUST:

Restore filesystem snapshot

Restore DB dump

Restore sandbox digest

Restore manifests

Restore environment lock

Verify CEO signature on AMU₀

Rollback count rules MUST be implemented:

1 automatic rollback allowed

Further rollbacks require CEO authorization

Rollback MUST be deterministic.

13. LOGGING

Antigravity MUST implement deterministic log formats with:

sequence_id

config SHA256

environment SHA256

FSM transitions

DB transaction logs

Gate results

Replay results

Rollback logs

Logs MUST be immutable and sorted.

14. OUTPUT ARTEFACTS

Antigravity MUST produce:

14.1 Final COO Runtime Spec (regenerated)

Regeneration MUST follow the COO Runtime Spec v1.0 generation template.

14.2 Implementation Pack (this document)

MUST be included in final migration bundle.

14.3 Migration Log Bundle

Contains:

All logs

Diff files

Manifests

Checksums

Replay results

Gate summaries

15. PROHIBITED ACTIONS

Antigravity MUST NOT:

Interpret governance logic

Infer missing intent

Skip steps

Execute nondeterministic sequences

Use heuristics

Allow environment drift

Allow sandbox rebuilds during Freeze

Allow deletion outside declared directories

END OF IMPLEMENTATION PACK v1.0