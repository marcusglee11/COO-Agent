# Project Build Summary

## 1. Overview
The `coo-agent` project is a multi-agent autonomous system. The current build state reveals a **critical structural divergence** that must be addressed immediately.

## 2. Repository Structure
The project currently contains two parallel codebase structures:

### A. `coo/` (Active Application)
- **Status**: The actual running application.
- **Entrypoint**: `coo.main` (verified via `python -m coo.main`).
- **Components**: `orchestrator.py`, `sandbox.py`, `message_store.py`, etc.
- **Issue**: **Does NOT contain the Phase 3 Fix Pack changes.** The governance logic, FSM transaction fixes, and sandbox hardening are missing from this directory.

### B. `project_builder/` (Shadow Codebase)
- **Status**: A disconnected directory structure.
- **Components**: `orchestrator/`, `sandbox/`, `config/`.
- **Issue**: **Contains the Phase 3 Fix Pack changes.** The recent work (governance.py, FSM fixes, tests) was applied here. This code is **not executed** by the main application.

### C. `config/` & `docker/`
- Shared configuration and Docker resources.
- `Dockerfile.sandbox` was updated correctly (it's at the root/docker level).

## 3. Documentation
- **README.md**: Describes the `coo/` architecture but was recently updated to claim features (Governance, Digest Pinning) that are currently implemented only in the shadow `project_builder/` codebase.
- **ARCHITECTURE.md**: Accurately describes the `coo/` architecture.
- **docs/**: Contains `governance_digest.md` (valid, but references `project_builder`).

## 4. Critical Issues & Suggestions

### 🚨 CRITICAL: Codebase Split-Brain
The "Phase 3 Fix Pack" was applied to `project_builder/`, but the application runs from `coo/`.
- **Impact**: The production application is **vulnerable**. It lacks the governance checks, FSM transaction safety, and sandbox hardening promised in the R2 review.
- **Remediation**:
    1.  **Port Fixes**: Move `governance.py`, `fsm.py` logic, and `runner.py` logic from `project_builder/` to their equivalents in `coo/`.
    2.  **Update Tests**: Refactor `tests/test_enforce_governance.py` to import from `coo` instead of `project_builder`.
    3.  **Delete Shadow Code**: Remove `project_builder/` to prevent recurrence.

### ⚠️ Testing Gap
- The governance tests pass, but they test the *shadow code*, not the *production code*.
- **Suggestion**: Implement a "sanity check" test that asserts the application entrypoint imports the expected modules.

### 💡 Improvements
- **Unified Config**: `coo/main.py` loads config from `config/`. Ensure the new `governance.py` is properly integrated into this loading flow.
- **Dependency Management**: `requirements.txt` should be audited to ensure no dependencies were introduced in `project_builder` that are missing from the main env (though none were observed).

## 5. Roadmap Alignment
- **Strategy**: "Deterministic Agent Runtime" with hard governance.
- **Current Build**: The *intent* matches the strategy, but the *implementation* is currently fragmented.
- **Next Step**: We must execute a **Consolidation Phase** to merge `project_builder` features into `coo` before proceeding to any new features.
