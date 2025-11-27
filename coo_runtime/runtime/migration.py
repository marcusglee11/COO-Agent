import os
import shutil
import logging
import subprocess
import sys
from typing import List
from .state_machine import RuntimeFSM, RuntimeState, GovernanceError
from .rollback import RollbackEngine

class MigrationEngine:
    """
    Executes the canonical 7-step PB -> COO migration sequence.
    Enforces atomicity and sorted traversal.
    Triggers Rollback on any failure.
    """

    def __init__(self, fsm: RuntimeFSM, rollback_engine: RollbackEngine):
        self.fsm = fsm
        self.rollback_engine = rollback_engine
        self.logger = logging.getLogger("MigrationEngine")

    def execute_migration_phase_1(self, pb_root: str, coo_root: str, test_runner_script: str) -> None:
        """
        Executes Steps 1-5 and 7 (Non-destructive to PB).
        """
        self.fsm.assert_state(RuntimeState.MIGRATION_SEQUENCE)
        self.logger.info("Starting Migration Phase 1 (Steps 1-5, 7)")
        
        # B2: Enforce pinned context before migration
        from ..util.context import apply_pinned_context
        try:
            apply_pinned_context("amu0_capture/pinned_context.json")
            self.logger.info("Pinned context applied successfully")
        except Exception as e:
            self.logger.error(f"Failed to apply pinned context: {e}")
            raise GovernanceError(f"Pinned context enforcement failed: {e}")

        try:
            # Step 1: Create canonical coo/ tree
            self._step_1_create_coo_tree(coo_root)

            # Step 2: Deterministically port PB code -> coo/ (Sorted Traversal)
            self._step_2_port_pb_code(pb_root, coo_root)

            # Step 3: Update test imports to coo.*
            self._step_3_update_test_imports(coo_root)

            # Step 4: Run full test suite (Snapshot A)
            self._step_4_run_tests_snapshot_a(test_runner_script)

            # Step 5: Update production imports to coo
            self._step_5_update_prod_imports(coo_root)

            # Step 7: Run full test suite (Snapshot B) - Moved before Step 6
            self._step_7_run_tests_snapshot_b(test_runner_script)

            self.logger.info("Migration Phase 1 Completed Successfully.")

        except Exception as e:
            self.logger.error(f"Migration Phase 1 Failed at step: {e}")
            self.logger.info("Initiating Rollback to AMU0...")
            self.rollback_engine.execute_rollback()
            raise GovernanceError(f"Migration Failed & Rolled Back: {e}")

    def finalize_migration_cleanup(self, pb_root: str):
        """
        Executes Step 6: Delete project_builder/ (Destructive).
        Should be called ONLY after Gates A-E pass.
        """
        # We might be in GATES state now, so we don't assert MIGRATION_SEQUENCE.
        self.logger.info("Starting Migration Cleanup (Step 6)")
        
        try:
            # Step 6: Delete project_builder/ directory
            self._step_6_delete_project_builder(pb_root)
            self.logger.info("Migration Cleanup Completed.")
        except Exception as e:
            self.logger.error(f"Migration Cleanup Failed: {e}")
            self.rollback_engine.execute_rollback()
            raise GovernanceError(f"Cleanup Failed & Rolled Back: {e}")

    def _step_1_create_coo_tree(self, coo_root: str):
        self.logger.info("Step 1: Creating canonical coo/ tree")
        if not os.path.exists(coo_root):
            os.makedirs(coo_root)
        
        # Create required subdirs
        for subdir in ["runtime", "orchestrator", "sandbox"]:
            os.makedirs(os.path.join(coo_root, subdir), exist_ok=True)

    def _step_2_port_pb_code(self, pb_root: str, coo_root: str):
        self.logger.info("Step 2: Porting PB code -> coo/ (Sorted Traversal)")
        
        # Canonical Sorted Traversal
        for root, dirs, files in os.walk(pb_root):
            dirs.sort() # Sort directories in-place for deterministic traversal
            files.sort() # Sort files
            
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, pb_root)
                dest_path = os.path.join(coo_root, rel_path)
                
                dest_dir = os.path.dirname(dest_path)
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                    
                shutil.copy2(src_path, dest_path)

    def _step_3_update_test_imports(self, coo_root: str):
        self.logger.info("Step 3: Updating test imports to coo.*")
        # Replace 'project_builder' with 'coo' in all .py files in coo/tests (if ported)
        # Assuming tests are inside coo/tests or similar.
        # If tests are external, we need to know where they are.
        # Assuming they were ported to coo/tests.
        self._replace_in_dir(coo_root, "project_builder", "coo")

    def _step_4_run_tests_snapshot_a(self, runner_script: str):
        self.logger.info("Step 4: Running Test Suite (Snapshot A)")
        try:
            subprocess.run([sys.executable, runner_script], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Tests Snapshot A Failed: {e}")

    def _step_5_update_prod_imports(self, coo_root: str):
        self.logger.info("Step 5: Updating production imports to coo")
        # Already done in Step 3 if we did it for all files?
        # Spec distinguishes test vs prod imports.
        # We just run replacement on the whole coo tree again to be sure.
        self._replace_in_dir(coo_root, "project_builder", "coo")

    def _step_6_delete_project_builder(self, pb_root: str):
        self.logger.info("Step 6: Deleting project_builder/")
        if os.path.exists(pb_root):
            shutil.rmtree(pb_root)

    def _step_7_run_tests_snapshot_b(self, runner_script: str):
        self.logger.info("Step 7: Running Test Suite (Snapshot B)")
        try:
            subprocess.run([sys.executable, runner_script], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Tests Snapshot B Failed: {e}")

    def _replace_in_dir(self, root_dir: str, old: str, new: str):
        for root, _, files in os.walk(root_dir):
            files.sort()
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    new_content = content.replace(old, new)
                    
                    if new_content != content:
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new_content)
