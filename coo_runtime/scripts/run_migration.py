import sys
import os
import argparse
import logging

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.runtime.rollback import RollbackEngine
from coo_runtime.runtime.replay import ReplayEngine
from coo_runtime.runtime.gates import GateKeeper

def main():
    parser = argparse.ArgumentParser(description="Run COO Migration (PB -> COO)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without changes")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("RunMigration")

    fsm = RuntimeFSM()
    
    # F5: Remove Fast-Forward. Assert State.
    # The system must already be in CAPTURE_AMU0 state (via previous operations or persistence).
    # If FSM initializes to INIT and doesn't load state, this will fail in a fresh run.
    # This is intended behavior for R5 compliance: scripts cannot arbitrarily jump states.
    if fsm.current_state != RuntimeState.CAPTURE_AMU0:
        logger.critical(f"Governance Error: Migration script started in invalid state: {fsm.current_state}. Expected: {RuntimeState.CAPTURE_AMU0}")
        sys.exit(1)

    rollback = RollbackEngine(fsm)
    migration = MigrationEngine(fsm, rollback)
    replay = ReplayEngine(fsm)
    gate_keeper = GateKeeper(fsm, replay)

    try:
        pb_root = os.path.abspath("project_builder")
        coo_root = os.path.abspath("coo")
        manifests_dir = os.path.abspath("manifests")
        test_runner = os.path.abspath("coo_runtime/scripts/run_tests.py")

        if args.dry_run:
            logger.info("DRY RUN: Migration sequence would execute here.")
            return

        # 1. Transition to MIGRATION_SEQUENCE
        # This is a legal transition from CAPTURE_AMU0
        fsm.transition_to(RuntimeState.MIGRATION_SEQUENCE)

        # 2. Migration Phase 1 (Steps 1-5, 7)
        migration.execute_migration_phase_1(pb_root, coo_root, test_runner)
        
        # 3. Transition to GATES
        fsm.transition_to(RuntimeState.GATES)
        
        # 4. Pre-Replay Gates (A-E)
        gate_keeper.run_pre_replay_gates(coo_root, manifests_dir, test_runner)
        
        # 5. Finalize Cleanup (Step 6 - Delete PB)
        migration.finalize_migration_cleanup(pb_root)
        
        # 6. Replay Gate (F)
        gate_keeper.run_replay_gate(coo_root, manifests_dir)
        
        # 7. Transition to CEO_FINAL_REVIEW (B6: REPLAY state removed)
        fsm.transition_to(RuntimeState.CEO_FINAL_REVIEW)
        logger.info("Migration and Gates Complete. Entering CEO_FINAL_REVIEW state.")

    except GovernanceError as e:
        logger.critical(f"Governance Failure: {e}")
        try:
            rollback.execute_rollback()
        except Exception as rb_e:
            logger.critical(f"Rollback Failed during Governance Failure: {rb_e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"Unhandled Exception: {e}")
        try:
            rollback.execute_rollback()
        except Exception as rb_e:
            logger.critical(f"Rollback Failed during Unhandled Exception: {rb_e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
