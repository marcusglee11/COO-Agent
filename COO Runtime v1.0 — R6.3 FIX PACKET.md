COO Runtime v1.0 — R6.3 FIX PACKET (Final, Binding)

Authority Chain:
LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0 → R5 Fix Packet (Binding) → R6.2 Fix Packet (Final) → Gate 1–7 Unified Review (Binding).

This R6.3 Fix Packet supersedes R6.2 where contradictions arise and is fully binding for the implementer (Antigravity). No deviation is permitted without explicit CSO/Alignment authorization.

====================================================================

SECTION A — BINDING AMU₀, FREEZE & IDENTITY FIXES

====================================================================

A1. Canonical AMU₀ Bundle Definition (Freeze Contract)

The AMU₀ canonical bundle MUST include ONLY:

All files in the AMU₀ directory EXCEPT:

rollback_log.jsonl

rollback_log.sig

signature.sig (bundle signature)

amu0_id.txt (this file is removed in A3)

Any .tmp files created by atomic-write operations.

The rollback log is explicitly excluded from the canonical bundle and is defined as associated metadata.

A2. Canonical Hash Function Update

calculate_canonical_hash() MUST:

Traverse directory tree with sorted ordering.

Normalize mtimes (315532800).

Exclude all files listed in A1 explicitly.

Produce SHA-256 digest.

A3. AMU₀ ID Derivation Simplification

amu0_id.txt MUST be removed entirely from AMU₀.

AMU₀ ID = first 16 hex characters of the canonical hash.

AMU₀ tracker MUST store and verify this derived ID.

All verification flows MUST recompute the ID rather than load it from a file.

A4. Unification of AMU₀ Verification

Implement a canonical function:

verify_amu0_complete(amu0_path) -> VerificationResult


This function MUST:

Verify directory structure.

Confirm required files and folder layout.

Compute canonical hash.

Validate bundle signature.

Validate rollback log integrity (see A5).

Confirm derived ID matches tracker entry.

All components MUST call this function instead of maintaining local variants.

A5. Rollback Log as Signed Metadata

Rollback log MUST:

Reside in AMU₀ directory.

Be append-only.

Use separate signature over full log content (rollback_log.sig).

NOT influence canonical hash or AMU₀ ID.

Be verified before rollback.

A6. Atomic Rollback Log Writes

Rollback log updates MUST follow:

Write updated log to rollback_log.jsonl.tmp

Generate signature to rollback_log.sig.tmp

Atomically rename both .tmp files into place.

This guarantees the log is never present in an unsigned or inconsistent state.

====================================================================

SECTION B — HARDWARE, PLATFORM, & PINNED CONTEXT

====================================================================

B1. Real Hardware Capture (No Placeholders)

During AMU₀ capture:

kernel_version MUST be captured using platform.release().

cpu_microcode MUST be captured using /proc/cpuinfo (or equivalent deterministic Linux path).

If either cannot be captured, the runtime MUST raise GovernanceError and abort capture.

B2. Linux-Only Enforcement at Entry

Add a platform gate at the earliest import point (coo_runtime/__init__.py).
If sys.platform != "linux", raise ImportError.

Remove all other platform checks throughout the codebase.

B3. Centralized Runtime Initialization

Implement:

initialize_runtime(amu0_path)


Which MUST:

Load pinned context.

Verify hardware context (B1).

Seed RNG with deterministic seed.

Enable libfaketime (if configured).

Call _verify_time_pinning() (B4).

Fail if ANY enforcement step does not apply cleanly.

All deterministic operations MUST be preceded by this call.

B4. Time Pinning Verification

Implement _verify_time_pinning(env, expected_time):

Spawn subprocess using pinned env.

Compare time.time() to pinned timestamp.

Difference > 1s MUST raise GovernanceError.

A failing FakeTime environment MUST not continue.

B5. Pinned Subprocess Isolation

Introduce:

run_pinned_subprocess(cmd, amu0_path, **kwargs)


All subprocess calls MUST use this helper (git, OCI, tests, replay, etc.).
Direct usage of subprocess.run, check_output, or Popen is forbidden.

====================================================================

SECTION C — ROLLBACK & RECOVERY

====================================================================

C1. Mandatory Staging Hash Verification

_verify_staging_integrity() MUST:

Compute canonical AMU₀ hash from source.

Compute canonical hash of staging directory.

Compare — mismatch MUST raise GovernanceError.

Only after passing, atomic rename to promote staging to AMU₀.

C2. Rollback Log Verification Before ANY Recovery Operation

Before ANY rollback step occurs:

Validate rollback log signature.

Validate hash chain.

Validate entry ordering.

Fail-closed on ANY inconsistency.

====================================================================

SECTION D — KEY MANAGEMENT & SIGNATURE PROTOCOL

====================================================================

D1. Canonical Key Resolution (No Fallbacks)

crypto.py MUST define:

get_ceo_private_key_path()
get_ceo_public_key_path()


Rules:

Keys MUST ONLY be specified via environment variables.

No repository paths.

No fallback search order.

Missing environment variable or file MUST fail-closed.

D2. Unified Signature Protocol

Implement:

class Signature:
    sign_data(...)
    verify_data(...)
    sign_file(...)
    verify_file(...)


ALL signing and verification (AMU₀, rollback, checkpoints, gates) MUST use this unified protocol.

====================================================================

SECTION E — SANDBOX & EXTERNAL TOOL VALIDATION

====================================================================

E1. Strict Sandbox Enforcement

Gate D MUST:

Attempt Docker inspect.

Attempt Podman inspect.

If both fail → GovernanceError("Sandbox unavailable").

No mock digests or fallback behaviours permitted.

E2. Pinned PATH for External Tools

run_pinned_subprocess MUST override PATH to a pinned, deterministic set of directories derived from AMU₀ context.

====================================================================

SECTION F — FSM, CHECKPOINTS & QUESTION MAPPING

====================================================================

F1. Clear Checkpoint Temporal Model

FSM MUST implement:

Checkpoints occur on transition out of designated states:

CAPTURE_AMU0

GATES

CEO_FINAL_REVIEW

Manual checkpointing is removed.

F2. Auto-Checkpointing in transition_to()

When leaving a checkpointable state:

_auto_checkpoint(f"after_{state.name}")

F3. Explicit QUESTION Mapping Table

Alignment Layer MUST define:

CONDITION → QUESTION_TYPE


Examples:

AMU₀ integrity failure → QUESTION_AMU0_INTEGRITY

Hardware mismatch → QUESTION_HARDWARE_PINNING

Sandbox unavailable → QUESTION_SANDBOX_SECURITY

Key mismatch → QUESTION_KEY_MANAGEMENT

Code MUST raise error→map→QUESTION consistently.

====================================================================

APPENDIX — RECOMMENDED NON-BINDING ENHANCEMENTS (D1–D5)

====================================================================

These improvements are optional for R6.3 but strongly recommended for R6.4.

D1. End-to-End Core Flow Narrative

Freeze → AMU₀ Capture → Gates → Replay → Rollback.

D2. Single Definition of AMU₀

Clarify canonical bundle vs metadata vs tracker relationships.

D3. Determinism Taxonomy

Document all determinism dimensions and enforcement mechanisms.

D4. Central “Pinned Context” Specification

Provide one canonical document clearly describing enforcement/dependencies.

D5. Dev vs Prod Policy

Define whether any dev-only exceptions are allowed and how they are mechanically fenced from prod.

====================================================================
END OF R6.3 FIX PACKET