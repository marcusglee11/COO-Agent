import unittest
import os
import sys
import json
import shutil
import tempfile
import hashlib
from unittest.mock import patch, MagicMock

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState, GovernanceError
from coo_runtime.runtime.gates import GateKeeper
from coo_runtime.runtime.amu_capture import AMUCapture
from coo_runtime.util import amu0_utils
from coo_runtime.util.context import enforce_pinned_context_or_fail
from coo_runtime.runtime.replay import ReplayEngine

class TestR6IntegrationDeterminism(unittest.TestCase):
    """
    Integration tests for R6 Blocking Fixes (WS-A to WS-E).
    Verifies determinism, security, and Linux-only enforcement.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.manifests_dir = os.path.join(self.test_dir, "manifests")
        os.makedirs(self.manifests_dir)
        self.coo_root = os.path.join(self.test_dir, "coo")
        os.makedirs(self.coo_root)
        
        # Create dummy manifests
        with open(os.path.join(self.manifests_dir, "environment_manifest.json"), "w") as f:
            json.dump({"allowed_env_vars": ["PATH"], "rng_seed": 12345, "mock_time": "1000"}, f)
            
        with open(os.path.join(self.manifests_dir, "sandbox_manifest.json"), "w") as f:
            json.dump({"image_sha256": "sha256:1234567890abcdef"}, f)
            
        with open(os.path.join(self.manifests_dir, "governance_ruleset.json"), "w") as f:
            f.write("{}")

        self.fsm = RuntimeFSM()
        # Force state to GATES for testing
        self.fsm._RuntimeFSM__current_state = RuntimeState.GATES

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        # Clean up global tracker if created
        if os.path.exists("active_amu0.json"):
            os.remove("active_amu0.json")

    def test_linux_only_enforcement(self):
        """
        Verify that pinned context enforcement fails on non-Linux platforms.
        (WS-B.2)
        """
        # Create dummy AMU0
        amu0_path = os.path.join(self.test_dir, "amu0_test")
        os.makedirs(amu0_path)
        with open(os.path.join(amu0_path, "pinned_context.json"), "w") as f:
            json.dump({"rng_seed": 1, "env_vars": {}}, f)

        if sys.platform != "linux":
            with self.assertRaises(GovernanceError) as cm:
                enforce_pinned_context_or_fail(amu0_path)
            self.assertIn("Unsupported platform", str(cm.exception))
        else:
            # On Linux, it should proceed (or fail on hardware check if not mocked)
            # We expect it to reach hardware check
            try:
                enforce_pinned_context_or_fail(amu0_path)
            except GovernanceError as e:
                # It might fail on kernel/microcode check, which is fine, 
                # as long as it passed the platform check.
                self.assertNotIn("Unsupported platform", str(e))

    def test_gate_d_real_sandbox_sha(self):
        """
        Verify Gate D queries Docker and enforces SHA match.
        (WS-B.1)
        """
        gate_keeper = GateKeeper(self.fsm)
        
        # Mock subprocess.run in gates.py
        # Since gates.py imports subprocess, we patch the module in that namespace
        with patch("coo_runtime.runtime.gates.subprocess.run") as mock_run:
            # Case 1: Match
            mock_run.return_value = MagicMock(stdout="sha256:1234567890abcdef\n", returncode=0)
            gate_keeper._gate_d_sandbox_security(self.manifests_dir)
            
            # Case 2: Mismatch
            mock_run.return_value = MagicMock(stdout="sha256:WRONG_HASH\n", returncode=0)
            with self.assertRaises(GovernanceError) as cm:
                gate_keeper._gate_d_sandbox_security(self.manifests_dir)
            self.assertIn("Sandbox SHA mismatch", str(cm.exception))
            
            # Case 3: Docker Missing (Fail Closed A.5)
            mock_run.side_effect = FileNotFoundError
            with self.assertRaises(GovernanceError) as cm:
                gate_keeper._gate_d_sandbox_security(self.manifests_dir)
            self.assertIn("Gate D Failed: OCI Runtime (Docker/Podman) unavailable", str(cm.exception))

    def test_gate_b_ast_security(self):
        """
        Verify Gate B detects forbidden imports and dynamic execution.
        (WS-D.2)
        """
        gate_keeper = GateKeeper(self.fsm)
        
        # Create malicious file
        malicious_file = os.path.join(self.coo_root, "malicious.py")
        
        # Case 1: Forbidden Import
        with open(malicious_file, "w") as f:
            f.write("import importlib\n")
        with self.assertRaises(GovernanceError) as cm:
            gate_keeper._gate_b_deterministic_modules(self.coo_root)
        self.assertIn("Forbidden import 'importlib'", str(cm.exception))
        
        # Case 2: Dynamic Execution (exec)
        with open(malicious_file, "w") as f:
            f.write("exec('print(1)')\n")
        with self.assertRaises(GovernanceError) as cm:
            gate_keeper._gate_b_deterministic_modules(self.coo_root)
        self.assertIn("Forbidden function call 'exec'", str(cm.exception))

    def test_dual_mode_replay_args(self):
        """
        Verify ReplayEngine passes correct mode to harness.
        (WS-C.1)
        """
        replay_engine = ReplayEngine(self.fsm)
        
        # Mock dependencies
        replay_engine._verify_reference_mission = MagicMock()
        replay_engine._compare_outputs = MagicMock(return_value=True)
        
        # Mock enforce_pinned_context_or_fail to return dummy env
        with patch("coo_runtime.runtime.replay.enforce_pinned_context_or_fail", return_value={}) as mock_ctx:
            with patch("subprocess.run") as mock_run:
                # Run Fast Mode
                replay_engine.execute_replay("mission.json", "amu0_path", mode="fast")
                
                # Verify subprocess call args
                args, kwargs = mock_run.call_args
                cmd = args[0]
                self.assertIn("--mode", cmd)
                self.assertIn("fast", cmd)
                
                # Run Deep Mode
                replay_engine.execute_replay("mission.json", "amu0_path", mode="deep")
                args, kwargs = mock_run.call_args
                cmd = args[0]
                self.assertIn("deep", cmd)

    def test_amu0_integrity_hashing(self):
        """
        Verify AMU0 hashing includes required files and excludes others.
        (WS-A.3)
        """
        amu0_path = os.path.join(self.test_dir, "amu0_integrity")
        os.makedirs(amu0_path)
        
        # Create required files
        for f in ["amu0_id.txt", "pinned_context.json", "snapshot_manifest.json", 
                  "phase3_reference_mission.json", "rollback_log.jsonl", "governance_rules_frozen.json"]:
            with open(os.path.join(amu0_path, f), "w") as fh:
                fh.write("content")
                
        # Calculate hash
        hash1 = amu0_utils.hash_directory_recursive(amu0_path)
        
        # Modify excluded file (signature.sig)
        with open(os.path.join(amu0_path, "signature.sig"), "w") as f:
            f.write("signature")
        hash2 = amu0_utils.hash_directory_recursive(amu0_path)
        
        self.assertEqual(hash1, hash2, "Signature file should be excluded from hash")
        
        # Modify required file
        with open(os.path.join(amu0_path, "rollback_log.jsonl"), "w") as f:
            f.write("modified")
        hash3 = amu0_utils.hash_directory_recursive(amu0_path)
        
        self.assertNotEqual(hash1, hash3, "Rollback log must be included in hash")

if __name__ == "__main__":
    unittest.main()
