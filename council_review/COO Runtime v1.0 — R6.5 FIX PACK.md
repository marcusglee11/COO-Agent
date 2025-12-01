# COO Runtime v1.0 — R6.5 FIX PACK (Integrated Council + CSO Binding Requirements)

Supersedes R6.4 Fix Packet
Authority Chain:
LifeOS v1.1 → Alignment Layer v1.4 → Runtime Spec v1.0 → Implementation Packet v1.0 → CSO Rulings (R6.4)

This Fix Pack eliminates all Critical and binding defects identified in R6.4, incorporates CSO constitutional rulings, and defines the full set of mechanical behaviours required for the R6.5 corrective build.
A Fix Pack can only be accepted when zero Critical defects remain (CSO ruling).

Structure matches prior A–H schema for continuity.

## A. AMU₀ INTEGRITY
### A1. Single Canonical Verification Entry Point
- All AMU₀ verification must route through `verify_amu0_complete()`.
- Remove all local AMU₀-checking logic across rollback, replay, gates, and tests.

### A3. Atomic, Hermetic AMU₀ Capture (Mandatory)
The runtime must implement:
- Temp capture pattern:
  ```python
  temp_dir = create_temp_amu0_dir()
  populate(temp_dir)
  verify_amu0_complete(temp_dir)
  os.replace(temp_dir, AMU0_PATH)
  ```
- Absolutely no incremental writes into AMU0_PATH.
- Hermeticity requirements:
  - Reject *.tmp, symlinks, extra files, or directories not explicitly part of AMU₀.
  - No rollback_log.* or signature.* inside AMU₀ (during capture).
  - Re-verify canonical hash post-promotion.

### A4. Canonical Deep Replay Trace
- Capture deterministic replay trace (`external_trace.jsonl`) into AMU₀.
- Include it in canonical AMU₀ hash.
- Treat it as immutable.

## B. TRACKER & ACTIVE AMU₀ PATH
### B1. Canonical Resolver Only
- Only `resolve_amu0_path()` may return active AMU₀.
- Remove legacy direct reads of tracker files.

### B2. Tracker Signature Binding
- Tracker JSON must include:
  - AMU₀ ID
  - canonical hash
  - state metadata
- Sign tracker JSON with `Signature.sign_data()`.
- Verify tracker signature before use; mismatches raise `QUESTION_ROLLBACK_INTEGRITY`.

## C. ROLLBACK INTEGRITY
### C1. Atomic Log + Signature Promotion
- Log and signature must be written to temp files and atomically promoted together.

### C2. Simplified Single-File Bounded Rollback Log (CSO Ruling)
- **Multi-file rotation removed.**
- Use a single `rollback.log`:
  - Deterministic constant `MAX_ROLLBACK_ENTRIES`.
  - Append-only.
  - When full: deterministic prune behaviour (drop oldest entry) or explicit fail-closed (choose one, document it).
- A hash-chain or equivalent integrity mechanism must bind all entries.

### C3. Append-Only Enforcement
- Any non-append modification must raise `QUESTION_ROLLBACK_INTEGRITY`.

## D. HARDWARE PINNING
### D1. Unified Hardware Capture
- All hardware capture must call `capture_hardware_context()`.

### D2. Mechanical-Only Verification (No Governance Logic)
- `_verify_hardware_context()` performs byte-equality only.
- Any mismatch → `QUESTION_HARDWARE_PINNING`, including "MICROCODE_UNKNOWN".
- No runtime interpretation of sentinel semantics.

## E. INITIALIZATION & DETERMINISM
### E1. Mandatory Initialization for All Deterministic Flows (Tests Included)
- All tests, gates, flows must begin with `initialize_runtime(amu0_path)`.
- Tests must fail if initialization is missing.

### E2. Remove All Legacy Init Helpers
- Delete `enforce_pinned_context_or_fail` and any bypass flags.

## F. SUBPROCESS ISOLATION & TIME PINNING
### F1. Exclusive Use of `run_pinned_subprocess()`
- Remove all direct subprocess/OCI calls.
- Time pinning, faketime, namespace restrictions, and env pinning must be enforced inside `run_pinned_subprocess()`.

### F2. Deterministic Time-Drift Detection
- Threshold is implementation-level, not constitutional. Default: 1s, or lower if stable.
- Any drift violation → `QUESTION_ENVIRONMENT_PINNING`.

## G. SIGNATURE & KEY MANAGEMENT
### G1. Unified API Only
- All signature operations must use `Signature.sign_data()` and `Signature.verify_data()`.

### G2. Key Management Model (CSO — Constitutional)
- **This is now required:**
  - Env specifies private key location ONCE at initialization.
  - Runtime loads private key material into memory-only structures.
  - Signature API must never accept private key paths.
  - No module may resolve private key paths after initialization.
  - Attempted key-path usage must fail deterministically.

## H. QUESTION ROUTING
### H1. Complete, Mechanical QUESTION Routing
- Runtime must perform no inference: QUESTION type must be explicit at call site.
- QUESTION set may be extended (CSO ruling), but must be deterministic and documented.
- All invariant failures must route through `raise_question(QUESTION_*, ...)` including:
  - AMU₀ failures
  - rollback integrity
  - hardware pinning
  - replay mismatch
  - sandbox violations
  - environment pinning
  - mode violations
  - key/signature failures
- Remove dynamic behaviour in `raise_question()`.
