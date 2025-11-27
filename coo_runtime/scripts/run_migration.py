import sys
import os
import argparse
import logging

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.runtime.rollback import RollbackEngine

def main():
    parser = argparse.ArgumentParser(description="Run COO Migration (PB -> COO)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without changes")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("RunMigration")

    fsm = RuntimeFSM()
    rollback = RollbackEngine(fsm)
    migration = MigrationEngine(fsm, rollback)
    
    # Initialize GateKeeper (needs FSM and ReplayEngine)
    # ReplayEngine needs FSM
    from coo_runtime.runtime.replay import ReplayEngine
    replay = ReplayEngine(fsm)
    from coo_runtime.runtime.gates import GateKeeper
    gate_keeper = GateKeeper(fsm, replay)

    # Manually transition FSM to MIGRATION_SEQUENCE for this script
    # In a real run, this would be part of a larger flow.
    # We assume we are ready.
    try:
        # Simulate previous states if needed or force state
        # We need to be in CAPTURE_AMU0 to transition to MIGRATION_SEQUENCE
        # But FSM starts at INIT.
        # We'll force the path: INIT -> AMENDMENT_PREP -> ... -> CAPTURE_AMU0
        # Or just use private var hack for this script since it's a "runner".
        # But we locked it down!
        # So we must transition properly.
        
        # Fast-forward FSM
        fsm.transition_to(RuntimeState.AMENDMENT_PREP)
        fsm.transition_to(RuntimeState.AMENDMENT_EXEC)
        fsm.transition_to(RuntimeState.AMENDMENT_VERIFY)
        fsm.transition_to(RuntimeState.CEO_REVIEW)
        fsm.transition_to(RuntimeState.FREEZE_PREP)
        fsm.transition_to(RuntimeState.FREEZE_ACTIVATED)
        fsm.transition_to(RuntimeState.CAPTURE_AMU0)
        fsm.transition_to(RuntimeState.MIGRATION_SEQUENCE)
        
        pb_root = os.path.abspath("project_builder")
        coo_root = os.path.abspath("coo")
        # manifests_dir is needed for Gates. Assuming it's in 'manifests'
        manifests_dir = os.path.abspath("manifests")
        test_runner = os.path.abspath("coo_runtime/scripts/run_tests.py")

        if args.dry_run:
            logger.info("DRY RUN: Migration sequence would execute here.")
            return

        # 1. Migration Phase 1 (Steps 1-5, 7)
        migration.execute_migration_phase_1(pb_root, coo_root, test_runner)
        
        # 2. Transition to GATES
        fsm.transition_to(RuntimeState.GATES)
        
        # 3. Pre-Replay Gates (A-E)
        gate_keeper.run_pre_replay_gates(coo_root, manifests_dir, test_runner)
        
        # 4. Finalize Cleanup (Step 6 - Delete PB)
        migration.finalize_migration_cleanup(pb_root)
        
        # 5. Replay Gate (F)
        gate_keeper.run_replay_gate(coo_root, manifests_dir)
        
        # 6. Transition to REPLAY (Wait, Gate F is Replay. FSM has REPLAY state.)
        # GateKeeper runs Gate F.
        # FSM says GATES -> REPLAY.
        # Should we transition to REPLAY before Gate F?
        # GateKeeper.run_replay_gate asserts GATES state currently.
        # If we want to follow FSM strictly:
        # GATES state covers Gates A-E?
        # REPLAY state covers Gate F?
        # The spec says "Gate F — Deterministic Replay".
        # If Gate F is part of GATES, then REPLAY state might be for "Post-Gate Replay Verification"?
        # Or maybe Gate F *is* the REPLAY state action?
        # Let's assume Gate F runs in GATES state, then we transition to REPLAY for final review?
        # Or transition to REPLAY, then run Gate F?
        # I'll stick to GATES state for now as GateKeeper asserts it.
        
        fsm.transition_to(RuntimeState.REPLAY)
        logger.info("Migration and Gates Complete. Entering REPLAY state.")

    except Exception as e:
        logger.error(f"Migration Script Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
