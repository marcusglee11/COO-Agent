R6.3 FIX PACK — CONSOLIDATED & FINAL
============================
Purpose

To correct all identified structural, deterministic, and governance defects in the COO Runtime v1.0 implementation.
All requirements are binding.
This packet fully integrates:

R6.3 Fix Packet (Blocking Items)

All CSO Constitutional Rulings

All Council findings across Architect, Alignment, Technical, Risk, Red-Team, and Simplicity

All QUESTION resolutions

No redesigns.
No behavioural changes except where constitutionally mandated.
Must be implemented exactly.

======================================
SECTION A — AMU₀ Integrity & Canonical Hash
======================================
Goal

Guarantee that AMU₀ is a fully deterministic, immutable, byte-frozen canonical bundle with no race windows, no partial writes, and no diverging verification paths.

Constitutional Ruling

AMU₀ consists only of the canonical bundle.

Rollback logs, trackers, and other runtime metadata are non-canonical metadata, not part of the hash.

Staging directories are optional, not constitutionally required.

Binding Directives
A1 — Single Canonical Verification Entry Point

All AMU₀ verification MUST be performed via:

verify_amu0_complete(amu0_path) -> VerificationResult


No other verification logic may exist.

Directives:

Remove local verification in: rollback.py, replay_harness.py, gates.py, tests.

Replace all signature/hash checks with a single call to the canonical verifier.

Verification failure must route into QUESTION_AMU0_INTEGRITY.

A2 — Canonical Hash Enforcement

The AMU₀ canonical hash must exclude exactly:

rollback_log.jsonl

rollback_log.sig

signature.sig

metadata/

all *.tmp files

all cache/temp files inside AMU₀

tracker files

any non-mission/non-FSM artefacts

The hash must be computed over a fully-frozen temp bundle.

A3 — Atomic AMU₀ Capture (No Staging Required)

The runtime MUST:

Construct AMU₀ inside a deterministic temp directory.

Run canonical verification on that temp directory.

Atomically promote via:

os.replace(temp_dir, AMU0_PATH)


Never write incrementally into AMU₀_PATH.

If verification fails → AMU₀_PATH remains unchanged.

A4 — Deep Replay Trace Canonicalisation

external_trace.jsonl MUST:

Be copied into AMU₀ during capture.

Never change after capture.

Be included in canonical hashing.

Implementation Notes

Ensure capture is hermetic: no symlinks, no nondeterministic timestamps.

Derive AMU₀ ID = first 16 hex of canonical hash (lowercase).

Integration Points

Replaces all staging logic from R6.2/6.3.

Simplifies capture_amu0.py and migration pipeline.

Consumes CSO ruling for QUESTION_AMU0_INTEGRITY.

Deterministic Test Requirements

Two sequential captures must yield byte-identical AMU₀.

Crash during capture must leave existing AMU₀ untouched.

Hash of temp directory = hash of final AMU₀.

======================================
SECTION B — AMU₀ Tracker & Path Resolution
======================================
Goal

Ensure a single canonical mechanism for resolving the active AMU₀ and guarantee its metadata integrity.

Constitutional Ruling

Tracker is metadata, not part of canonical hash.

Tracker must be cryptographically bound to AMU₀.

Binding Directives
B1 — Canonical Resolver Only

Only the following function may return an AMU₀ path:

resolve_amu0_path()


Directives:

Remove all direct file reads of active_amu0_path.json.

Enforce resolve_amu0_path() for all callers.

Add assertion/decorator for functions requiring resolved AMU₀.

B2 — Tracker Signature Binding

Tracker must contain:

AMU₀_ID

AMU₀_HASH

runtime state metadata

monotonic index

Tracker must be signed with:

Signature.verify_data(tracker_json, tracker_sig)


Changes to AMU₀ must invalidate tracker signature.

Integration Points

Consolidates all path handling into amu0_utils.

Eliminates any legacy file formats.

Deterministic Test Requirements

Modifying AMU₀ must cause tracker verification to fail.

Resolving path twice must yield same value.

======================================
SECTION C — Rollback Integrity
======================================
Goal

Make rollback atomic, verifiable, and tamper-evident with no partial states and deterministic recovery.

Constitutional Ruling

Hash-chain is optional, not required.

Full-log signature + append-only semantics are sufficient.

Rollback logs must have bounded size.

Binding Directives
C1 — Atomic Rollback Log Promotion

Rollback log (rollback_log.jsonl) and signature must be promoted together atomically via:

os.replace() on a directory containing both files, or

RENAME_EXCHANGE

No scenario may exist where log is present without signature.

C2 — Log Bloat Limits

Rollback log must have hard bounds:

Max size: 10 MB

On overflow: rotate → rollback_log.1

Write continuity-marker binding their signatures

C3 — Append-Only

Any non-append modification → immediate QUESTION_ROLLBACK_INTEGRITY.

Integration Points

Removes staging-verification of rollback logs.

Simplifies rollback engine.

Deterministic Tests

Overflow rotation deterministic across runs.

Log+signature always pair-valid.

======================================
SECTION D — Hardware Pinning
======================================
Goal

Ensure fully deterministic hardware fingerprints across freeze, replay, and AMU₀ capture.

Constitutional Ruling

Missing microcode is not a failure.

Use deterministic sentinel: "MICROCODE_UNKNOWN".

Fail-closed only if kernel_version is missing.

Binding Directives
D1 — Hardware Capture Only in capture_hardware_context()

All modules must call:

capture_hardware_context()


No inline parsing of /proc/cpuinfo.

D2 — Deterministic Sentinels

If microcode missing:

hardware_fingerprint.microcode = "MICROCODE_UNKNOWN"


Value must be frozen into AMU₀.

Integration Points

Applies to replay, freeze, and migration logic.

Aligns with CSO ruling for QUESTION_HARDWARE_PINNING.

Deterministic Tests

Same environment must always yield same fingerprint.

Environments with missing microcode must match sentinel version exactly.

======================================
SECTION E — Determinism Scope & Initialization
======================================
Goal

Guarantee that all deterministic operations run inside a fully pinned environment.

Constitutional Ruling

All deterministic flows (including tests) must call initialize_runtime().

There are no exceptions.

Binding Directives
E1 — Mandatory Initialization

Before any deterministic execution:

initialize_runtime(amu0_path)


Tests must not bypass initialization.

E2 — Remove Deprecated Initialization Paths

Delete:

enforce_pinned_context_or_fail

older init helpers

test bypass flags

Integration Points

Affects test harness, replay, gates, rollback, migration.

Deterministic Tests

All tests must start with initialization.

Environment fingerprints must be identical across test runs.

======================================
SECTION F — Subprocess Isolation & Time Pinning
======================================
Goal

Guarantee deterministic subprocess behaviour across replay, gates, and sandbox verification.

Constitutional Ruling

All OCI tools, Docker/Podman included, must run through run_pinned_subprocess.

No deviations permitted.

Binding Directives
F1 — Exclusive Subprocess API

All subprocess calls must use:

run_pinned_subprocess()


Remove all direct uses of:

subprocess.run

subprocess.check_output

subprocess.Popen

asyncio.create_subprocess_exec (unless internally pinned)

F2 — Strengthened Time Pinning

_verify_time_pinning must:

Confirm LD_PRELOAD faketime injection works.

Detect real wall-clock leakage.

Fail if drift > 1 second.

Integration Points

Enforces determinism across Gate D.

Implements CSO ruling for QUESTION_ENVIRONMENT_PINNING.

Deterministic Tests

Same OCI commands must yield byte-for-byte identical output across runs.

======================================
SECTION G — Signature & Key Management
======================================
Goal

Ensure unified, safe, deterministic signature mechanisms.

Constitutional Ruling

Signature API may accept explicit public key paths only.

It must never accept private keys.

Zero-config (env-only) is the default.

Binding Directives
G1 — Unified Signature Protocol

Remove:

sign_bytes

verify_signature

any legacy signature APIs

All signing must be via:

Signature.sign_data(data)


All verification via:

Signature.verify_data(data, sig)

G2 — Key Path Restrictions

Signature API must:

Load private keys from env only.

Reject private key paths if passed.

Accept public key override (optional).

Integration Points

Simplifies crypto.py

Removes historical key-handling logic

Deterministic Tests

Attempting to provide a private key path must deterministically fail.

Verification must succeed deterministically with env-driven keys.

======================================
SECTION H — QUESTION Routing
======================================
Goal

Enforce constitutional governance routing for all structural/invariant failures.

Constitutional Ruling

QUESTION routing is mandatory for all ambiguity and invariant failures.

Binding Directives
H1 — Mandatory QUESTION Mapping

Replace all raw GovernanceError in invariant contexts with:

raise_question(QUESTION_TYPE, ...)


Mapping must cover:

AMU₀ integrity

Hardware pinning

Sandbox security

Replay mismatch

Rollback integrity

Key/signature errors

Mode violations

Environment pinning failures

Integration Points

Affects gates, replay engine, rollback engine, init, and AMU₀ capture.

Deterministic Tests

All invariant failures must produce deterministic QUESTION_TYPE values.