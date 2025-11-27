import os
import sys
import shutil
import json
import logging
import subprocess
import unittest
import hashlib
from typing import Dict, Any

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.runtime.rollback import RollbackEngine
from coo_runtime.runtime.gates import GateKeeper
from coo_runtime.runtime.replay import ReplayEngine
from coo_runtime.runtime.amu_capture import AMUCapture

class TestE2EProofOfLife(unittest.TestCase):

    def setUp(self):
        self.test_dir = "e2e_test_env"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        # Setup directories
        self.pb_root = os.path.join(self.test_dir, "project_builder")
        self.coo_root = os.path.join(self.test_dir, "coo")
        self.manifests_dir = os.path.join(self.test_dir, "manifests")
        self.amu_dir = os.path.join(self.test_dir, "amu0_capture")
        
        os.makedirs(self.pb_root)
        os.makedirs(self.manifests_dir)
        
        # Create dummy PB content
        with open(os.path.join(self.pb_root, "main.py"), "w") as f:
            f.write("print('Hello from PB')\n")
            
        # Create dummy manifests
        with open(os.path.join(self.manifests_dir, "environment_manifest.json"), "w") as f:
            json.dump({
                "allowed_env_vars": ["PATH", "HOME"],
                "rng_seed": "TEST_SEED",
                "mock_time": "2025-01-01T00:00:00Z"
            }, f)
            
        with open(os.path.join(self.manifests_dir, "hardware_manifest.json"), "w") as f:
            json.dump({}, f)
            
        with open(os.path.join(self.manifests_dir, "sandbox_manifest.json"), "w") as f:
            json.dump({"image_sha256": "SHA256_TEST"}, f)
            
        with open(os.path.join(self.manifests_dir, "governance_ruleset.json"), "w") as f:
            json.dump([], f)
            
        # Create dummy reference mission
        self.mission_path = os.path.join(self.test_dir, "phase3_reference_mission.json")
        with open(self.mission_path, "w") as f:
            f.write(json.dumps({"mission": "test"}))
            
        # Create dummy test runner
        self.test_runner = os.path.join(self.test_dir, "run_tests.py")
        with open(self.test_runner, "w") as f:
            f.write("print('Tests Passed')\n")
            
        # Create dummy coo directory
        if not os.path.exists(self.coo_root):
            os.makedirs(self.coo_root)
        with open(os.path.join(self.coo_root, "orchestrator.py"), "w") as f:
            f.write("# Dummy Orchestrator\n")
            
        # Capture AMU0 (Mocking the capture process or using the class)
        capture = AMUCapture()
        # We need to change CWD to test_dir for relative paths to work if needed, 
        # but AMUCapture takes args.
        # AMUCapture writes to "amu0_capture" in CWD.
        # We should probably run this test in self.test_dir.
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Capture AMU0
        capture.capture_amu0("manifests", "phase3_reference_mission.json")
        
        # Create signature
        with open("amu0_capture/signature.sig", "w") as f:
            f.write("MOCK_SIG")

    def tearDown(self):
        os.chdir(self.original_cwd)
        # shutil.rmtree(self.test_dir) # Keep for inspection if failed

    def test_full_migration_success(self):
        print("\n--- Testing Full Migration Success (R3) ---")
        
        fsm = RuntimeFSM()
        rollback = RollbackEngine(fsm)
        migration = MigrationEngine(fsm, rollback)
        replay = ReplayEngine(fsm)
        gate_keeper = GateKeeper(fsm, replay)
        
        # Fast forward FSM
        self._fast_forward_fsm(fsm)
        
        # 1. Phase 1
        migration.execute_migration_phase_1("project_builder", "coo", "run_tests.py")
        
        # 2. Transition
        fsm.transition_to(RuntimeState.GATES)
        
        # 3. Pre-Replay Gates
        gate_keeper.run_pre_replay_gates("coo", "manifests", "run_tests.py")
        
        # 4. Cleanup
        migration.finalize_migration_cleanup("project_builder")
        
        # 5. Replay Gate
        # Mock Orchestrator imports if needed, or rely on them being present.
        # Since we are running in the repo root context, it should find 'coo'.
        gate_keeper.run_replay_gate("coo", "manifests")
        
        # Verify
        self.assertTrue(os.path.exists("coo"))
        self.assertFalse(os.path.exists("project_builder"))
        self.assertTrue(os.path.exists("replay_output_run1"))
        
        # Verify AMU0 Snapshot (R3)
        self.assertTrue(os.path.exists("amu0_capture/fs_snapshot"))
        self.assertTrue(os.path.exists("amu0_capture/snapshot_manifest.json"))
        self.assertTrue(os.path.exists("amu0_capture/signature.sig"))

    def test_rollback_snapshot_corruption(self):
        print("\n--- Testing Rollback Snapshot Corruption (R3) ---")
        
        fsm = RuntimeFSM()
        rollback = RollbackEngine(fsm)
        migration = MigrationEngine(fsm, rollback)
        replay = ReplayEngine(fsm)
        gate_keeper = GateKeeper(fsm, replay)
        
        self._fast_forward_fsm(fsm)
        
        # Run migration to create snapshot
        migration.execute_migration_phase_1("project_builder", "coo", "run_tests.py")
        
        # Corrupt Snapshot
        with open("amu0_capture/fs_snapshot/project_builder/main.py", "w") as f:
            f.write("CORRUPTED")
            
        # Trigger Rollback via Gate Failure
        fsm.transition_to(RuntimeState.GATES)
        shutil.rmtree("coo") # Fail Gate A
        
        # Expect Rollback to Fail due to signature verification failure
        # With real crypto (B1), corrupting the snapshot invalidates the signature
        # So we expect signature verification to fail before snapshot hash check
        with self.assertRaises(GovernanceError) as cm:
            try:
                gate_keeper.run_pre_replay_gates("coo", "manifests", "run_tests.py")
            except GovernanceError:
                rollback.execute_rollback()
                
        # B1: Real crypto detects corruption via signature, not hash check
        self.assertIn("Signature Verification Failed", str(cm.exception))

    def test_strict_mode_enforcement(self):
        print("\n--- Testing Strict Mode Enforcement (R3) ---")
        
        fsm = RuntimeFSM()
        
        # Fast forward to CEO_REVIEW
        fsm.transition_to(RuntimeState.AMENDMENT_PREP)
        fsm.transition_to(RuntimeState.AMENDMENT_EXEC)
        fsm.transition_to(RuntimeState.AMENDMENT_VERIFY)
        
        # Try transition to CEO_REVIEW without strict mode
        if "COO_STRICT_MODE" in os.environ:
            del os.environ["COO_STRICT_MODE"]
            
        with self.assertRaises(GovernanceError) as cm:
            fsm.transition_to(RuntimeState.CEO_REVIEW)
        self.assertIn("Strict Mode Required", str(cm.exception))
        
        # Enable Strict Mode
        os.environ["COO_STRICT_MODE"] = "1"
        
        # Create new FSM since previous one is in ERROR state
        fsm = RuntimeFSM()
        fsm.transition_to(RuntimeState.AMENDMENT_PREP)
        fsm.transition_to(RuntimeState.AMENDMENT_EXEC)
        fsm.transition_to(RuntimeState.AMENDMENT_VERIFY)
        
        fsm.transition_to(RuntimeState.CEO_REVIEW)
        self.assertEqual(fsm.current_state, RuntimeState.CEO_REVIEW)
        
        del os.environ["COO_STRICT_MODE"]

    def test_replay_failure_nondeterminism(self):
        print("\n--- Testing Replay Failure (Nondeterminism) ---")
        # R3: Replay uses Orchestrator. Nondeterminism is harder to inject without mocking the mock.
        # But we can mock the ReplayEngine._run_mission to return different DBs.
        
        fsm = RuntimeFSM()
        replay = ReplayEngine(fsm)
        gate_keeper = GateKeeper(fsm, replay)
        
        self._fast_forward_fsm(fsm)
        fsm.transition_to(RuntimeState.GATES)
        
        # Mock _run_mission
        original_run = replay._run_mission
        def mock_run(mission_path, run_id):
            try:
                out = original_run(mission_path, run_id)
                # Modify DB to cause mismatch
                import sqlite3
                db_path = os.path.join(out, "mission.db")
                conn = sqlite3.connect(db_path)
                conn.execute(f"UPDATE missions SET description = description || '_nondet_{run_id}'")
                conn.commit()
                conn.close()
                return out
            except Exception as e:
                print(f"DEBUG: mock_run failed: {e}")
                raise e
            
        replay._run_mission = mock_run
        
        with self.assertRaises(GovernanceError) as cm:
            gate_keeper.run_replay_gate("coo", "manifests")
            
        self.assertIn("Deterministic Replay Failed", str(cm.exception))

    def _fast_forward_fsm(self, fsm):
        # R3: Strict mode required for some transitions
        os.environ["COO_STRICT_MODE"] = "1"
        try:
            fsm.transition_to(RuntimeState.AMENDMENT_PREP)
            fsm.transition_to(RuntimeState.AMENDMENT_EXEC)
            fsm.transition_to(RuntimeState.AMENDMENT_VERIFY)
            fsm.transition_to(RuntimeState.CEO_REVIEW)
            fsm.transition_to(RuntimeState.FREEZE_PREP)
            fsm.transition_to(RuntimeState.FREEZE_ACTIVATED)
            fsm.transition_to(RuntimeState.CAPTURE_AMU0)
            fsm.transition_to(RuntimeState.MIGRATION_SEQUENCE)
        finally:
            # Clean up env var to avoid polluting other tests
            if "COO_STRICT_MODE" in os.environ:
                del os.environ["COO_STRICT_MODE"]

if __name__ == "__main__":
    unittest.main()
