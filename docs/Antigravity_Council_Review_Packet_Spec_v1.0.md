ANTIGRAVITY COUNCIL REVIEW PACKET SPEC v1.0

Authority Chain:
LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0 → Antigravity Instruction Packet (Phase 4) → this Review Packet Spec.

Status: Subordinate, mechanical, non-governance.
Scope: Applies to all COO Runtime / PB→COO builds performed under the Phase 4 Instruction Packet (and later phases that extend the runtime).

0. Purpose

This spec defines how you MUST generate a single consolidated Council Review Packet text artefact immediately after each successful Phase build (Phase 1–Phase N) of the COO Runtime work.

The packet is for Council code reviews. It MUST:

Provide the Council a deterministic, self-contained snapshot of the build,

Include a mechanical walkthrough mapped to the implementation plan / build phases,

Include the flattened codebase for the incremental build scope,

Avoid any governance decisions, verdicts, or interpretation of constitutional authority.

You generate documentation only; you do NOT judge or approve anything.

1. Subordination & Role Boundaries

LifeOS v1.1, Alignment Layer v1.4, COO Runtime Spec v1.0, Implementation Packet v1.0, and the Antigravity Instruction Packet all supersede this document in case of conflict.

You MUST treat this spec as mechanical only:

You MAY describe what you implemented.

You MAY summarise code structure and behaviour.

You MUST NOT:

Issue Accept / Go With Fixes / Reject verdicts.

Decide whether invariants are satisfied.

Alter governance rules or Council protocol.

Any ambiguity in this spec → you emit a clearly marked “OPEN_QUESTION” section for the Council rather than resolving it.

2. When to Generate a Review Packet

You MUST generate a Council Review Packet whenever ALL of the following are true:

A Phase build completes successfully under the Phase 4 Instruction Packet (e.g. “Phase 2 — Manifests & Environment Lock”, “Phase 3 — Core Runtime Components”, etc.).

The build produced at least one of:

New files in the COO Runtime tree or related scripts/tests, or

Modifications to existing COO Runtime / PB / migration / sandbox code, or

Changes to manifests or test harnesses relevant to determinism, sandboxing, or migration.

The build has a unique identifier (e.g. Git commit SHA or equivalent).

You MUST NOT skip packet generation for a qualifying Phase build.

3. Output Format & Location

3.1 File Format

Single UTF-8 text file.

Canonical name pattern:

council_review/COO_Runtime_Phase<PHASE>_Build_<BUILD_ID>_ReviewPacket_v1.0.txt

Examples:

council_review/COO_Runtime_Phase2_Build_ab12cd3_ReviewPacket_v1.0.txt

council_review/COO_Runtime_Phase4_Build_main_2025-11-28_ReviewPacket_v1.0.txt

3.2 Determinism Requirements

Sections MUST appear in the exact order defined in Section 4.

Within each section, any lists (files, tests, functions) MUST be:

Sorted lexicographically by path/name.

Generated from a deterministic traversal (e.g. sorted(os.walk(...))).

Packet content MUST be reproducible for identical repo state + configuration.

4. Packet High-Level Structure

You MUST emit the following top-level sections in order, with exact headings:

# 0. PACKET METADATA

# 1. BUILD CONTEXT & AUTHORITY

# 2. IMPLEMENTATION PLAN MAPPING

# 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE)

# 4. TESTS, GATES & DETERMINISM SURFACE

# 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS

# 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)

# 7. OPEN QUESTIONS & IMPLEMENTER NOTES

Each section below is mandatory, even if some subsections are marked “NONE”.

5. Section Definitions
5.1 # 0. PACKET METADATA

You MUST include:

Phase: (e.g. Phase 3 — Core Runtime Components)

Build_ID: (commit SHA or equivalent)

Timestamp_UTC: (ISO string; may be derived deterministically from CI metadata)

Repo_Path: (logical project name)

Spec_Versions: list:

LifeOS_v1.1

Alignment_Layer_v1.4

COO_Runtime_Spec_v1.0

Implementation_Packet_v1.0

Antigravity_Instruction_Packet_Phase4_v1.0

Scope: brief mechanical description (e.g. “Phase 3 runtime modules + tests for determinism and migration”).

No interpretation or verdicts here; this is pure metadata.

5.2 # 1. BUILD CONTEXT & AUTHORITY

You MUST mechanically restate:

Authority Chain (one short paragraph re-stating subordination, citing the canonical specs).

Phase Goals (Mechanical):

Extract the relevant Phase description from the Antigravity Instruction Packet and quote/summarise it deterministically (non-normative).

Files Touched (Summary Table):

A small table or bullet list of:

ADDED_FILES:

MODIFIED_FILES:

DELETED_FILES:

Paths MUST be sorted.

You MUST NOT alter any spec language when restating authority or scope.

5.3 # 2. IMPLEMENTATION PLAN MAPPING

Purpose: allow the Council to see what you claim to have implemented vs which plan/spec sections you followed.

You MUST include:

Plan Artefact References:

Filenames and (if available) headings for:

The relevant Implementation Packet sections.

Any Phase-specific implementation plan document(s) you were given (file names only; include content only if requested by the CEO via configuration).

Phase-to-Code Mapping Table

A structured table with columns:

Plan_Section

Brief_Mechanical_Description

Key_Files_Implemented

For example:

Plan_Section: "4. AMENDMENT ENGINE (MECHANICAL)"

Brief_Mechanical_Description: "Deterministic anchoring + amendment_log.json + amendment_diff.patch"

Key_Files_Implemented: ["coo_runtime/runtime/amendment_engine.py", "coo_runtime/tests/test_determinism.py"]

This table is descriptive only and MUST be derived from:

Plan section titles,

The actual file paths you changed.

No claims about correctness; only “we wired X plan section to these files”.

5.4 # 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE)

This is a narrative but non-binding walkthrough to help reviewers orient themselves.

You MUST:

Clearly label the section header as:

# 3. STRUCTURAL WALKTHROUGH (NON-NORMATIVE, DESCRIPTIVE ONLY)

For each key module touched in this phase (runtime file, script, or test), emit a short, structured entry:

Module_Path: ...

Role (from spec/plan): ... (pull language from spec/plan where possible)

Key_Public_Interfaces: [function/class names] (derived from parsing the file)

Notes: short 2–4 lines describing what the module appears to do, in neutral language.

Rules:

Do NOT claim “correctness”, “compliance”, or “passed verification”.

Use phrases like “implements”, “wires”, “provides functions for” rather than “ensures compliance”, “guarantees determinism”, etc.

If you are unsure, state: Notes: Unable to infer behaviour without governance; flagged for Council review.

5.5 # 4. TESTS, GATES & DETERMINISM SURFACE

You MUST help the Council see what is being exercised.

Tests Overview

List all tests run as part of the Phase build (e.g. pytest node IDs).

For each test file:

Test_File: ...

Test_Cases: list of function names or node IDs.

Result: PASS/FAIL/SKIPPED (from CI/logs).

Note: this is reporting only; no interpretation of adequacy.

Gates Touched (if any)

If this Phase includes or affects any Gates from the COO Runtime Spec (A–F), list which gate logic files were touched and how:

Gate: A — Repo Unification Integrity

Gate_Implementation_Files: [...]

Gate_Tests: [...] (if any)

Determinism Surface Notes

Mechanical, factual list of determinism-relevant behaviours:

RNG seeding behaviour (if present).

Time mocking or fixed timestamps.

File traversal ordering guarantees (sorted(...)).

Explicit environment pinning behaviours.

You MUST limit yourself to directly observable behaviours (e.g., “function X sets RNG seed to 0xDEADBEEF”) and MUST NOT assert that overall determinism is satisfied.

5.6 # 5. SANDBOX, FREEZE & AMU₀ TOUCHPOINTS

If the Phase modifies any of:

freeze.py

amu_capture.py

sandbox / OCI digests

manifests related to environment/hardware/freeze

you MUST document:

Relevant Files Changed

Manifest Fields Touched (e.g. tools_manifest.json, environment_manifest.json, sandbox_digest.txt, freeze_manifest.json).

AMU₀-Related Logic:

Where snapshots are taken.

Where SHA256 hashes are computed.

Where CEO signatures are expected/verified (paths and function names only).

If the Phase does not touch any of these, you MUST explicitly state:
This Phase did not modify sandbox, freeze, or AMU₀ logic.

5.7 # 6. FLATTENED CODEBASE (INCREMENTAL SCOPE)

This section MUST contain the entire flattened codebase for the incremental build scope only.

Scope Definition:

All files under the configured root(s) (e.g. coo_runtime/, selected PB/IP locations) that:

Were added or modified in this Phase build, OR

Are core runtime modules the Phase relies on and which the Council is likely to review together (default: all Python files in coo_runtime/runtime/, coo_runtime/tests/, coo_runtime/scripts/).

Format:

For each file included, you MUST emit:

===== FILE START: <relative/path/to/file.py> =====
<file contents, exactly as on disk>
===== FILE END: <relative/path/to/file.py> =====


Rules:

Files MUST be ordered lexicographically by path.

Contents MUST be byte-identical to the repo state used for the build.

You MUST NOT omit any file within the defined scope.

5.8 # 7. OPEN QUESTIONS & IMPLEMENTER NOTES

This is the only section where you MAY raise issues for the Council, but still without verdicts.

Subsections:

## 7.1 OPEN_QUESTIONS_FOR_COUNCIL

Each entry:

ID: Q-<incrementing integer>

Source: [file path + line range, or “config”]

Description: short neutral phrasing of the ambiguity or concern.

Evidence: specific references (e.g. functions, comments, manifest fields).

You MUST NOT recommend a decision; you only flag.

## 7.2 IMPLEMENTER_NOTES (NON-NORMATIVE)

Implementation notes such as:

“Unclear requirement in spec section X; implemented safest mechanical option Y.”

“Test harness relies on assumption Z; Council may wish to review.”

These notes are advisory and non-binding.

6. Mechanical Generation Process (High-Level)

To produce the packet, you MUST:

Capture build metadata (phase, commit, specs, timestamp).

Build file lists from the repo (added/modified/removed + core runtime scope).

Parse plan/spec references as needed for mapping.

Extract test execution results from CI logs.

Generate the narrative sections using deterministic prompts and config that emphasise non-normative, descriptive language.

Concatenate all sections in the defined order into a single text file.

Write to the council_review/ directory at the project root.

If any step fails, you MUST still attempt to emit a partial packet with a clear error note in Section 7.1.