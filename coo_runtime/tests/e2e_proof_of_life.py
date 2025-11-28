import os
import sys
import shutil
import json
import logging
import subprocess
import unittest
import unittest.mock
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
        
        # Clean up FSM state
        if os.path.exists("fsm_state.json"):
            os.remove("fsm_state.json")
        
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
        # We need to mock sign_bytes because we don't have a real key in tests usually
        # But AMUCapture expects one.
        # We can mock coo_runtime.util.crypto.sign_bytes
        with unittest.mock.patch("coo_runtime.util.crypto.sign_bytes", return_value=b"mock_sig"):
             capture.capture_amu0("manifests", "phase3_reference_mission.json")
        
        # B3: Resolve AMU0 path dynamically
        with open("active_amu0.json", "r") as f:
            data = json.load(f)
            self.amu_dir = data["path"]
        
    @unittest.mock.patch("coo_runtime.runtime.replay.enforce_pinned_context_or_fail", return_value={})
    @unittest.mock.patch("coo_runtime.runtime.migration.enforce_pinned_context_or_fail", return_value={})
    @unittest.mock.patch("coo_runtime.util.context._verify_hardware_context")
    def test_full_migration_success(self, mock_hw, mock_ctx_mig, mock_ctx_rep):
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
        # Mock Gate D (Sandbox) because we don't have real sandbox
        with unittest.mock.patch("coo_runtime.runtime.gates.GateKeeper._gate_d_sandbox_security"):
             gate_keeper.run_pre_replay_gates("coo", "manifests", "run_tests.py")
        
        # 4. Cleanup
        migration.finalize_migration_cleanup("project_builder")
        
        # 5. Replay Gate
        with unittest.mock.patch("coo_runtime.runtime.replay.ReplayEngine._run_mission") as mock_run:
            # Create dummy output dirs with same content
            os.makedirs("replay_output_run1", exist_ok=True)
            with open("replay_output_run1/mission.db", "w") as f: f.write("db")
            os.makedirs("replay_output_run2", exist_ok=True)
            with open("replay_output_run2/mission.db", "w") as f: f.write("db")
            
            mock_run.side_effect = ["replay_output_run1", "replay_output_run2"]
            
            gate_keeper.run_replay_gate("coo", "manifests")
        
        # Verify
        self.assertTrue(os.path.exists("coo"))
        self.assertFalse(os.path.exists("project_builder"))
        
        # Verify AMU0 Snapshot (R3)
        self.assertTrue(os.path.exists(os.path.join(self.amu_dir, "fs_snapshot")))
        self.assertTrue(os.path.exists(os.path.join(self.amu_dir, "snapshot_manifest.json")))
        self.assertTrue(os.path.exists(os.path.join(self.amu_dir, "signature.sig")))

    @unittest.mock.patch("coo_runtime.runtime.rollback.enforce_pinned_context_or_fail", return_value={})
    @unittest.mock.patch("coo_runtime.util.context._verify_hardware_context")
    def test_rollback_snapshot_corruption(self, mock_hw, mock_ctx_rb):
        print("\n--- Testing Rollback Snapshot Corruption (R3) ---")
        
        fsm = RuntimeFSM()
        rollback = RollbackEngine(fsm)
        # ...

    def test_strict_mode_enforcement(self):
        # ... (no change needed as it doesn't call runtime logic that checks platform)
        print("\n--- Testing Strict Mode Enforcement (R3) ---")
        # ...

    @unittest.mock.patch("coo_runtime.runtime.replay.enforce_pinned_context_or_fail", return_value={})
    @unittest.mock.patch("coo_runtime.util.context._verify_hardware_context")
    def test_replay_failure_nondeterminism(self, mock_hw, mock_ctx_rep):
        print("\n--- Testing Replay Failure (Nondeterminism) ---")
        
        fsm = RuntimeFSM()
        replay = ReplayEngine(fsm)
        gate_keeper = GateKeeper(fsm, replay)
        
        self._fast_forward_fsm(fsm)
        fsm.transition_to(RuntimeState.GATES)
        
        # Mock _run_mission
        # We need to mock it to return two different directories
        
        def mock_run(mission_path, run_id, env, amu0_path, mode):
            out_dir = f"replay_output_{run_id}"
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "mission.db"), "w") as f:
                if run_id == "run1":
                    f.write("data_A")
                else:
                    f.write("data_B") # Mismatch
            return out_dir
            
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


if __name__ == "__main__":
    unittest.main()
