# Repository Structure Proposal

## Current State
- **`coo/`**: Flat structure (`orchestrator.py`, `sandbox.py`). Active but missing features.
- **`project_builder/`**: Modular structure (`orchestrator/`, `sandbox/`, `database/`). Contains Phase 3 fixes but is inactive.

## Proposal: Modularize `coo/`
We should refactor `coo/` to match the modular structure of `project_builder/`. This allows us to drop-in the new components (Governance, FSM, Runner) cleanly.

### Target Structure (`coo/`)
```
coo/
├── __init__.py
├── main.py                 # Entrypoint (Keep)
├── config/                 # New: Governance & Settings
│   ├── __init__.py
│   ├── governance.py       # Ported from project_builder
│   └── settings.py         # Ported from project_builder
├── orchestrator/           # New: Modular Orchestrator
│   ├── __init__.py
│   ├── core.py             # Refactored from coo/orchestrator.py
│   └── fsm.py              # Ported from project_builder
├── sandbox/                # New: Modular Sandbox
│   ├── __init__.py
│   ├── runner.py           # Ported from project_builder
│   └── manifest.py         # Ported from project_builder
├── database/               # New: Database Utils
│   ├── __init__.py
│   └── timeline.py         # Ported from project_builder
├── agents/                 # Existing (Keep)
│   ├── base.py
│   └── real_agents.py
├── message_store.py        # Keep (or move to database/)
├── budget.py               # Keep
└── cli.py                  # Keep
```

## Migration Steps
1.  **Create Packages**: Create `coo/config`, `coo/orchestrator`, `coo/sandbox`.
2.  **Port Code**: Copy files from `project_builder` to their new homes in `coo`.
3.  **Refactor Main**: Update `coo/main.py` to import from new locations.
4.  **Delete Shadow**: Remove `project_builder`.
5.  **Cleanup**: Move root scripts to `scripts/`.
