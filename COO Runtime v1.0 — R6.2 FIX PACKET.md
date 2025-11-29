# COO Runtime v1.0 — **R6 FIX PACKET (FINAL)**

# Binding Constitutional, Alignment, Determinism, and Security Fixes

**Authority Chain (Binding):
LifeOS v1.1 → Alignment Layer v1.4 → COO Runtime Spec v1.0 → Implementation Packet v1.0 → R5 Fix Packet → R6 Fix Packet (Final).**

This R6 Fix Packet (Final) supersedes all earlier R6 drafts and incorporates the blocking issues from Gates 1–7.

All fixes are **mandatory**.
All mechanics are **deterministic**.
All structures must be implemented **exactly**.

---

# SECTION 0 — GLOBAL R6 REQUIREMENTS

R6 requires hardening of:

1. **AMU₀ integrity**
2. **Rollback determinism + safety**
3. **FSM governance correctness**
4. **Sandbox security**
5. **Replay determinism (Fast + Deep)**
6. **Pinned context (OS, hardware, env, time)**
7. **Key management (dev/prod separation)**
8. **Governance ruleset freeze**
9. **Migration determinism (AST-only)**
10. **Database determinism (SQLite PRAGMAs)**

Everything below is binding.

---

============================================================

# SECTION 1 — R6-F1: Rollback State Integrity (BLOCKING)

============================================================

### PROBLEM

* `rollback_state.json` is excluded from the AMU₀ signature → attacker can reset counter → infinite rollback.

### REQUIREMENTS (binding)

1. **Rollback state MUST be cryptographically verifiable, tamper-evident, and append-only.**
2. Must NOT rely on unsigned or plaintext counter files.
3. Must NOT rely on system time.
4. Must use **pinned/normalized time** from AMU₀.

### FIX (binding)

Implement a **hash-chained append-only rollback log**, placed inside AMU₀:

```
amu0_<id>/
   rollback_log.jsonl       (append-only)
   rollback_log.sig         (signature over full content)
```

Mechanics:

* Each entry includes:

  * `sequence_number: int`
  * `pinned_timestamp: str (ISO8601)`
  * `previous_hash: hex`
  * `entry_hash: hex`

* The log must be re-signed after each append.

* Any mismatch in chain → `GovernanceError`.

### Determinism Requirements

* `pinned_timestamp` comes **only** from `pinned_context.json` (mock_time).
* No `time.time()` calls allowed.
* JSON writing MUST use `sort_keys=True`.

---

============================================================

# SECTION 2 — R6-F2: Active AMU₀ Tracker (BLOCKING)

============================================================

### PROBLEM

* `active_amu0_path.txt` is unsigned → attacker substitutes an AMU₀.

### REQUIREMENTS

1. Tracker MUST be a **signed JSON object**:
   `active_amu0_path.json` + `active_amu0_path.json.sig`.

2. Fields:

   ```
   {
     "amu0_path": "<relative path>",
     "amu0_id": "<id>",
     "created_at": "<ISO8601 pinned timestamp>",
     "repo_commit": "<git SHA>"
   }
   ```

3. Verification MUST occur before **any** AMU₀ access.

4. ID must match the AMU₀’s `amu0_id.txt`.

---

============================================================

# SECTION 3 — R6-F3: FSM State Integrity (BLOCKING)

============================================================

### PROBLEM

* `fsm_state.json` is freely writable → attacker forges governance progress.

### R6 REQUIREMENTS

1. **Remove unverified fsm_state.json**.
2. Replace with **signed checkpoints only**, gated at constitutional transitions:

   * After **CAPTURE_AMU0**
   * After **GATES**
   * Before **CEO_FINAL_REVIEW**

Checkpoint files:

```
fsm_checkpoint_<name>.json
fsm_checkpoint_<name>.json.sig
```

### Verification requirements:

* Signed with CEO key
* Validated before loading state
* Must validate linear history against allowed transition graph

### Determinism requirements:

* Timestamps must come from `pinned_context.json`.

---

============================================================

# SECTION 4 — R6-F4: Hardware Context Enforcement (BLOCKING)

============================================================

### PROBLEM

* Kernel version and CPU microcode recorded as `"UNKNOWN"` → violates determinism.

### REQUIREMENTS

1. Hardware capture MUST fail closed if kernel/microcode cannot be retrieved.
2. Pinned context structure:

```
{
  "kernel_version": "<string>",
  "cpu_microcode": "<string>",
  "env_vars": {...},
  "rng_seed": "<int>",
  "mock_time": "<ISO8601>",
  ...
}
```

3. No Windows/macOS escapes permitted.
4. Constitutional rule: **Linux-only** for R6.

---

============================================================

# SECTION 5 — R6-F5: Replay Determinism (BLOCKING)

============================================================

### REQUIREMENTS

1. Implement **Deep-Mode external call recorder**:

   * During AMU₀ capture:

     * Record external calls (LLM, network, subprocess outputs) into `external_trace.jsonl`.
   * During Replay Deep Mode:

     * Read from trace and replay exactly.

2. Fast Mode remains permitted, but MUST be deterministic.

3. Replay must verify:

   * Byte-identical output_bundle directories
   * Deterministic DB files
   * Deterministic logs (no real-time stamps)

4. Time mocking MUST be effective (libfaketime verification step).

---

============================================================

# SECTION 6 — R6-F6: CEO Key Management (BLOCKING)

============================================================

### REQUIREMENTS

1. CEO private key MUST NOT reside in repository.

2. Mandatory environment variables:

   * `CEO_PRIVATE_KEY_PATH`
   * `CEO_PUBLIC_KEY_PATH`

3. Production signing MUST use HSM or equivalent external signer.

4. Dev mode MUST use clearly marked test keys; signatures must include metadata:

```
"dev_mode": true
```

---

============================================================

# SECTION 7 — R6-F7: Migration AST Determinism (BLOCKING)

============================================================

### REQUIREMENTS

1. Migration MUST be pure AST → AST transformation.
2. No string-based rewriting.
3. Must detect dynamic import patterns and fail with `GovernanceError`.
4. Output file MUST be generated with `ast.unparse()` or libcst equivalent.

---

============================================================

# SECTION 8 — R6-F8: Governance Ruleset Freeze (BLOCKING)

============================================================

### REQUIREMENTS

1. Governance ruleset MUST be copied into AMU₀ during capture:

```
governance_ruleset_frozen.json
```

2. Manifest must include its hash:

   * `governance_ruleset_sha256`

3. Gate E MUST use frozen version only.

4. Any mismatch → `GovernanceError`.

---

============================================================

# SECTION 9 — R6-F9: AMU₀ Deterministic Capture (BLOCKING)

============================================================

### REQUIREMENTS

1. Directory name MUST be deterministic, not UUID-based:

   ```
   amu0_<canonical_hash_prefix>
   ```

2. Snapshot metadata (mtimes) MUST be normalized, e.g.:

```
normalized_mtime = 315532800         # 1980-01-01
```

3. `json.dump(sort_keys=True)` mandatory across capture.
4. All non-deterministic fields must be excluded or normalized.

---

============================================================

# SECTION 10 — R6-F10: Sandbox Security (BLOCKING)

============================================================

### REQUIREMENTS

1. Gate D MUST query real OCI runtime:

   * docker inspect
   * podman inspect
   * fail closed if neither available

2. Env var spoofing MUST be removed.

3. Mock SHA fallback MUST be removed.

4. Expected SHA taken ONLY from manifest.

5. Mismatch → `GovernanceError` without fallback.

---

============================================================

# SECTION 11 — R6-F11: Context Isolation & Time Pinning (BLOCKING)

============================================================

### REQUIREMENTS

1. Replace in-process `os.environ.clear()` with **subprocess-isolated environment construction**.
2. `enforce_pinned_context_or_fail()` must return a clean environment dict.
3. Caller MUST pass the environment via `env=` to subprocesses.
4. libfaketime MUST be loaded explicitly via LD_PRELOAD.
5. A validation subprocess must confirm that `time.time()` reflects pinned time.

---

============================================================

# SECTION 12 — R6-F12: Test Suite Freeze (BLOCKING)

============================================================

### REQUIREMENTS

1. Introduce `test_manifest.json`:

```
{
  "test_runner_path": "...",
  "test_runner_sha256": "<hash>"
}
```

2. Gate C must verify hash before invoking tests.
3. Any mutation → `GovernanceError`.

---

============================================================

# SECTION 13 — R6-F13: Rollback Atomicity (BLOCKING)

============================================================

### REQUIREMENTS

1. Use a dedicated staging directory: `rollback_staging_atomic/`.
2. Copy files into staging.
3. Hash staging.
4. Compare to AMU₀ canonical hash.
5. Atomically rename into place with backup suffix.
6. Cleanup.

No direct copy from AMU₀ to production folders.

---

============================================================

# SECTION 14 — R6-F14: DB Determinism (BLOCKING)

============================================================

### REQUIREMENTS

1. Mandatory SQLite PRAGMAs:

```
PRAGMA journal_mode=DELETE;
PRAGMA synchronous=FULL;
PRAGMA temp_store=MEMORY;
PRAGMA locking_mode=EXCLUSIVE;
PRAGMA page_size=4096;
PRAGMA auto_vacuum=NONE;
```

2. ALL DB writes must occur under forced deterministic settings.
3. DB file must appear byte-identical across runs.

---

============================================================

# SECTION 15 — R6-F15: Subprocess Context Enforcement (BLOCKING)

============================================================

### REQUIREMENTS

1. All gates, replay, migration, test runner invocations MUST use:

```
env = enforce_pinned_context_or_fail(amu0_path)
subprocess.run(..., env=env)
```

2. No path may rely on inherited environment from parent.

---

============================================================

# SECTION 16 — R6-F16: Import Rewriting Coverage (BLOCKING)

============================================================

### REQUIREMENTS

1. Must detect dynamic import patterns:

* `__import__()`
* `importlib.import_module()`
* `eval("import ...")`
* `exec()`-based import constructs

2. These must result in `GovernanceError`.

---

# END OF R6 FIX PACKET (FINAL)

# ================================================================================

# COO Runtime v1.0

# **R6 IMPLEMENTATION PLAN (FINAL, ANTIGRAVITY-READY)**

================================================================================

This plan converts the R6 Fix Packet (Final) into explicit implementation tasks for Antigravity.

Each item includes:

* Files to modify
* New files to create
* Functions to replace or remove
* Required deterministic behavior
* Atomicity and safety constraints
* No placeholders

---

# SECTION A — IMPLEMENTATION OVERVIEW

Antigravity MUST update:

* `coo_runtime/util/`
* `coo_runtime/runtime/`
* `coo_runtime/migration/`
* `coo_runtime/replay/`
* `coo_runtime/sandbox/`
* `coo_runtime/rollback/`
* `coo_runtime/manifests/`
* `project_builder/`

All tasks MUST be implemented exactly and deterministically.

---

# SECTION B — DETAILED IMPLEMENTATION TASKS

Below is the full list of implementation actions required.

============================================================

## A1 — Active AMU₀ Tracker (Signed)

============================================================

Modify/add:

* `coo_runtime/util/amu0_utils.py`
* `coo_runtime/util/crypto.py`
* `coo_runtime/amu_capture.py`

Tasks:

1. Replace `active_amu0_path.txt` with `active_amu0_path.json` + `.sig`.
2. Add signature verification on load.
3. Add ID consistency check.
4. Add repo commit capture.
5. Use pinned timestamp.

---

============================================================

## A2 — Rollback Log (Hash-Chained, Signed)

============================================================

Modify/add:

* `coo_runtime/rollback/rollback_log.py` (new file)
* `coo_runtime/rollback/rollback.py`

Tasks:

1. Implement JSONL append-only log.
2. Enforce pinned timestamp.
3. Re-sign full log after append.
4. Validate hash chain on load.

---

============================================================

## A3 — FSM Governance Checkpoints (Signed)

============================================================

Modify/add:

* `coo_runtime/runtime/state_machine.py`

Tasks:

1. Remove old persistence.
2. Add checkpoint creation.
3. Add checkpoint verification.
4. Add transition-history validation.
5. Enforce checkpoints only at constitutional boundaries.

---

============================================================

## A4 — Pinned Context Enforcement (Subprocess-Isolated)

============================================================

Modify/add:

* `coo_runtime/util/context.py`
* All subprocess call sites (gates, migration, replay, test runner)

Tasks:

1. Convert enforcement to environment-builder function.
2. Add libfaketime detection.
3. Add time-freeze self-test.
4. Require all subprocesses to use enforced environment.

---

============================================================

## A5 — Sandbox Verification (OCI Required)

============================================================

Modify/add:

* `coo_runtime/runtime/gates.py`

Tasks:

1. Replace env-var verification with OCI inspect.
2. Add Docker + Podman fallback.
3. Fail closed if neither works.
4. Remove all mock SHA paths.

---

============================================================

## A6 — Migration (Pure AST)

============================================================

Modify:

* `coo_runtime/migration/migration.py`

Tasks:

1. Replace hybrid transformation with AST → AST.
2. Use ast.unparse() or libcst.
3. Identify dynamic imports → raise GovernanceError.

---

============================================================

## A7 — Deep Replay Mode (Recorder + Replayer)

============================================================

Modify/add:

* `coo_runtime/replay/replay.py`
* `coo_runtime/replay/external_trace_recorder.py`
* `coo_runtime/replay/external_trace_replayer.py`

Tasks:

1. Implement recorder during AMU₀ freeze.
2. Record all external calls:

   * LLM
   * network
   * subprocess outputs
3. Implement deterministic replayer for Deep Mode.
4. Update output bundle comparator to include external trace.

---

============================================================

## A8 — Deterministic DB Enforcement

============================================================

Modify:

* `coo_runtime/replay/replay_harness.py`

Tasks:

1. Apply PRAGMAs at DB creation time.
2. Enforce DB determinism contract.
3. Add validation that DB bytes match between runs.

---

============================================================

## A9 — Ruleset Freeze

============================================================

Modify:

* `coo_runtime/amu_capture.py`
* `coo_runtime/runtime/gates.py`

Tasks:

1. During capture:

   * Copy governance_ruleset.json → governance_ruleset_frozen.json
   * Store SHA in snapshot manifest

2. During Gate E:

   * Verify SHA
   * Use frozen copy exclusively

---

============================================================

## A10 — AMU₀ Deterministic Capture

============================================================

Modify:

* `coo_runtime/amu_capture.py`
* `coo_runtime/util/amu0_utils.py`

Tasks:

1. Remove UUID naming; use hash prefix.
2. Normalize mtimes.
3. Ensure JSON sorting.
4. Remove timestamp nondeterminism.
5. Exclude only signature.sig (and include rollback log).

---

============================================================

## A11 — Test Runner Freeze

============================================================

Modify/add:

* `coo_runtime/scripts/run_tests.py`
* `manifests/test_manifest.json`
* `coo_runtime/runtime/gates.py` (Gate C)

Tasks:

1. Add hash validation.
2. Fail closed if mismatch.

---

============================================================

## A12 — Atomic Rollback

============================================================

Modify:

* `coo_runtime/rollback/rollback.py`

Tasks:

1. Implement staging directory.
2. Re-hash staging.
3. Atomic rename.
4. Backup then clean up.

---

============================================================

## A13 — Dev/Prod Key Separation

============================================================

Modify:

* All locations loading keys
* `coo_runtime/util/crypto.py`

Tasks:

1. Remove keys from repo.
2. Require env var for private key.
3. Detect dev mode via metadata.
4. Require HSM in prod if possible.

---

============================================================

## A14 — Import Rewriting Validations

============================================================

Modify:

* `migration.py`

Tasks:

1. Add detection of dynamic import patterns.
2. Raise GovernanceError when detected.

---

============================================================

## A15 — Subprocess Enforcement Everywhere

============================================================

Modify:

* All gate functions
* All migration steps
* Replay engine
* Test runner invocation

Tasks:

1. Replace inherited environment with enforced one.
2. Add explicit `env=` usage.
3. Confirm pinned context applied.

---

# END OF R6 IMPLEMENTATION PLAN (FINAL)

================================================================================
