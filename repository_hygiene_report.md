# Repository Hygiene Report

## 1. Root File Inventory & Analysis

| File/Directory | Status | Required By | Action |
| :--- | :--- | :--- | :--- |
| `.env` | **Required** | Runtime (Config) | Keep |
| `.env.example` | **Required** | Runtime (Config) | Keep |
| `.git/` | **Required** | VCS | Keep |
| `.gitignore` | **Required** | VCS | Keep |
| `.pytest_cache/` | **Ignored** | Test Runner | Keep (Gitignored) |
| `ARCHITECTURE.md` | **Required** | Documentation | Keep |
| `FixPack_phase3_final.txt` | **Redundant** | Historical | Archive |
| `InitDBSchema.py` | **Redundant** | Legacy Script | Archive |
| `InspectScript.py` | **Redundant** | Legacy Script | Archive |
| `config/` | **Required** | Runtime | Keep |
| `coo/` | **Required** | Current Runtime | Keep (Target for Migration) |
| `coo_agent.egg-info/` | **Ignored** | Packaging | Keep (Gitignored) |
| `debug.db` | **Redundant** | Debugging | Delete |
| `debug_sandbox.py` | **Redundant** | Debugging | Archive |
| `demo_llm.py` | **Redundant** | Demo | Archive |
| `docker/` | **Required** | Runtime (Sandbox) | Keep |
| `docs/` | **Required** | Documentation | Keep |
| `final_remediation_packet.txt` | **Redundant** | Historical | Archive |
| `final_remediation_packet_v2.txt` | **Redundant** | Historical | Archive |
| `final_review_packet.txt` | **Redundant** | Historical | Archive |
| `final_test_output.txt` | **Redundant** | Historical | Archive |
| `impl/` | **Required** | Phase 4 Specs | Keep |
| `init_global_budget.py` | **Redundant** | Legacy Script | Archive |
| `inspect_latest_mission.py` | **Redundant** | Legacy Script | Archive |
| `multi_task_demo.py` | **Redundant** | Demo | Archive |
| `packet_final.txt` | **Redundant** | Historical | Archive |
| `packet_remediation.txt` | **Redundant** | Historical | Archive |
| `packet_remediation_fixed.txt` | **Redundant** | Historical | Archive |
| `prepare_review.py` | **Redundant** | Dev Tool | Archive |
| `project_builder/` | **Required** | Source for Migration | Keep (Until Migration Complete) |
| `project_summary.md` | **Redundant** | Phase 3 Artifact | Archive |
| `prompts/` | **Required** | Runtime | Keep |
| `pyproject.toml` | **Required** | Packaging | Keep |
| `readme.md` | **Required** | Documentation | Keep |
| `reinit_db.py` | **Redundant** | Legacy Script | Archive |
| `repository_structure_proposal.md`| **Redundant** | Phase 3 Artifact | Archive |
| `review.log` | **Redundant** | Historical | Archive |
| `review_packet*.txt` | **Redundant** | Historical | Archive |
| `seed_mission_*.py` | **Redundant** | Demo | Archive |
| `specs/` | **Required** | Phase 4 Specs | Keep |
| `test_budget_concurrency.db` | **Redundant** | Testing | Delete |
| `test_output*.txt` | **Redundant** | Historical | Archive |
| `tests/` | **Required** | Current Tests | Keep |
| `venv/` | **Ignored** | Environment | Keep (Gitignored) |

## 2. Cleanup Plan

### 2.1 Archive Strategy
Create a `legacy_archive/` directory to store historical artifacts and scripts that are not part of the runtime but should not be deleted yet.

### 2.2 Execution Steps
1.  Create `legacy_archive/`.
2.  Move all files marked **Archive** to `legacy_archive/`.
3.  Delete files marked **Delete**.
4.  Ensure `coo_runtime/` is created as a clean new root for Phase 4 work.

### 2.3 Verification
- Confirm no `Required` files are moved.
- Confirm root is clean except for: `coo/`, `config/`, `docker/`, `docs/`, `impl/`, `project_builder/`, `prompts/`, `specs/`, `tests/`, and standard dotfiles/metadata.
