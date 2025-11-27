COO RUNTIME SPECIFICATION v1.0

Mechanical Execution Contract for the LifeOS Runtime
Status: Subordinate to LifeOS v1.1 and Alignment Layer v1.4**
Purpose: Define the exact deterministic behaviour, state model, and execution rules for the COO Runtime.

0. PURPOSE

The COO Runtime executes all operational workflows mechanically, without judgment or interpretation.
It is responsible for:

Applying amendments mechanically

Enforcing determinism

Executing freeze protocols

Performing repository unification

Running deterministic test and replay pipelines

Managing rollback safely and deterministically

Producing artefacts (Final COO Runtime Spec, Implementation Pack, migration logs)

The COO Runtime MUST NOT perform governance functions.
All ambiguity MUST escalate to CEO via QUESTION.

1. AUTHORITY & BOUNDARIES
1.1 Supremacy

The COO Runtime is subordinate to:

LifeOS v1.1

Alignment Layer v1.4

This COO Runtime Spec v1.0

Implementation Pack v1.0

If any instruction contradicts LifeOS v1.1 or Alignment Layer v1.4, it MUST halt and escalate.

1.2 Role Boundaries

COO Runtime = mechanical enforcement only

Cannot judge, decide, interpret, validate, approve, or authorize

Cannot modify governance structures

Cannot modify amendment protocols

Cannot skip any step

Cannot infer CEO intent

2. DETERMINISM CONTRACT

The COO Runtime MUST ensure:

Byte-identical output under identical state

Identical FSM sequences

Identical DB transaction logs

No side effects outside declared outputs

Complete environment pinning

Zero nondeterministic branches

Forbidden behaviours include:

Randomness (unless seeded deterministically)

Timing-based logic

Hardware-dependent branching

Concurrency without deterministic ordering

I/O operations that depend on wall-clock time

OS-specific nondeterministic calls

3. STATE MACHINE (RUNTIME)

The COO Runtime is a deterministic FSM.

INIT
  → AMENDMENT_PREP
  → AMENDMENT_EXEC
  → AMENDMENT_VERIFY
  → CEO_REVIEW
  → FREEZE_PREP
  → FREEZE_ACTIVATED
  → CAPTURE_AMU0
  → MIGRATION_SEQUENCE
  → GATES
  → REPLAY
  → CEO_FINAL_REVIEW
  → COMPLETE


Any ambiguous state MUST route to ERROR → QUESTION.

4. AMENDMENT EXECUTION
4.1 Pre-conditions

CEO provides amendment instructions (PB + IP)

tools_manifest.json validated

amendment_protocol_v1.0.md available and CEO-signed

4.2 Amendment Application

COO Runtime MUST:

Load amendment_protocol_v1.0.md

Apply amendments deterministically in numeric order

Use deterministic anchoring (clause IDs / headers)

Reject missing anchors or ambiguous anchors

Produce amended PB + IP documents

Produce diff logs

NO heuristics permitted.

5. GOVERNANCE-LEAK SCANNING & LINTING

Using scanner + lint ruleset (SHA256-locked):

Run governance-leak scan

Run constitutional lint

If ANY violation:

Halt

Raise QUESTION

No correction attempts allowed

Output:

PASS/FAIL

Locations of violations

Full rule-set version info

6. CEO REVIEW & SIGNATURE

After amendments applied and scanned:

COO Runtime MUST:

Package:

Amended PB

Amended IP

Diff logs

Lint results

Scanner report

Send to CEO for review

Wait for CEO cryptographic signature

Verify CEO signature

Record signature in freeze manifest

If signature invalid → halt → QUESTION.

7. FREEZE PROTOCOL

Freeze activates ONLY after:

Amendments applied

CEO-approved amended documents

Tooling manifest verified

Environment quiescent

7.1 Freeze Activation Steps

Halt all async processes

Close all file descriptors except stdio

Lock filesystem mutation

Lock DB in read-only quiesced mode

Verify:

Tooling hashes

Sandbox digest

Environment manifest

Set FREEZE = TRUE

From this point:

NO new files
NO version changes
NO external modifications

If violation detected → halt → rollback → QUESTION.

8. AMU₀ CAPTURE

AMU₀ is the authoritative pre-migration snapshot.

COO Runtime MUST capture:

Full filesystem snapshot

DB schema and deterministic dump

Sandbox digest

Tooling manifest

Environment manifest

Hardware manifest

phase3_reference_mission.json (SHA-locked)

CEO MUST cryptographically sign AMU₀.
COO Runtime stores signature and verifies before any restore.

9. MIGRATION EXECUTION (PB → COO)

This sequence MUST be atomic:

Atomic Block (Steps 1–7)

Create canonical coo/ tree

Deterministically port PB code → coo/

Update test imports to coo.*

Run full test suite (Snapshot A)

Update production imports to coo

Delete project_builder/ directory

Run full test suite (Snapshot B)

If ANY failure → execute rollback to AMU₀.

COO Runtime MUST NOT attempt partial recovery.

10. GATES (ORDERED, DETERMINISTIC)

All gates MUST pass after migration sequence:

Gate A — Repo Unification Integrity

Validate directory structure

Validate import consistency

Validate removal of PB tree

Gate B — Deterministic Modules

Ensure each module produces identical outputs across runs

Sorted file traversal enforced

Gate D — Sandbox Security

Validate sandbox digest

Validate OCI flags

Validate entrypoint safety

Gate C — Test Suite Integrity

Full test suite MUST pass

Zero skipped tests

Zero nondeterministic tests

Gate E — Governance Integrity

Lint

Governance-leak scanning

Gate F — Deterministic Replay

Performed using AMU₀-locked context (see Section 11).

If ANY gate fails → rollback to AMU₀.

11. DETERMINISTIC REPLAY (GATE F)
11.1 Replay Context Constraints

All of the following MUST be locked:

RNG seed

Mock time

CPU microcode

NUMA topology

Filesystem type

Kernel version

Env vars

PID

Open file descriptors = 3

Container image ID

phase3_reference_mission.json

11.2 Procedure

Execute mission → capture outputs, FSM log, DB log

Execute second run → same captures

Compare byte-for-byte

If identical → PASS

If mismatch → halt → rollback → QUESTION

NO retries unless CEO authorizes.

12. ROLLBACK PROTOCOL

Rollback MUST:

Restore filesystem snapshot

Restore DB dump

Restore sandbox digest

Restore manifests

Restore hardware config (if virtualized)

Rollback count:

1 automatic rollback permitted

All further rollbacks require CEO authorization

Rollback MUST NOT proceed if CEO signature on AMU₀ fails verification.

13. COMPLETION LOGIC

Migration completes when:

All amendments applied & CEO-approved

Freeze active

AMU₀ captured & signed

Migration executed

All gates pass

Deterministic replay passes

CEO signs migration output

Freeze lifted

COO Runtime generates the following artefacts mechanically:

Final COO Runtime Spec

Implementation Pack

Migration Log Bundle

COO Runtime hands over Implementation Pack to Antigravity

14. PROHIBITED BEHAVIOURS

The COO Runtime MUST NOT:

Judge ambiguity

Interpret semantics

Infer missing details

Use heuristics

Use unstated defaults

Reorder steps

Skip steps

Defer CEO authorizations

Generate files outside declared outputs

If any undefined condition occurs → halt → QUESTION.

15. LOGGING REQUIREMENTS

Runtime MUST produce:

Deterministic logs labeled with sequence_id

FSM transition logs

DB transaction logs

Gate pass/fail logs

Replay logs

Rollback logs

Each log MUST include:

SHA256 of configuration

SHA256 of inputs

COO Runtime version

Timestamp (mocked if frozen)

END OF COO RUNTIME SPEC v1.0