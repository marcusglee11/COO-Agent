import unittest
import os
import hashlib
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.replay import ReplayEngine
from coo_runtime.runtime import init
from unittest.mock import patch, MagicMock

class TestReplay(unittest.TestCase):
    def setUp(self):
        self.fsm = RuntimeFSM()
        self.replay = ReplayEngine(self.fsm)
        
        # Mock AMU0
        self.amu0_path = "mock_amu0"
        os.makedirs(self.amu0_path, exist_ok=True)
        
        self.mission_path = "mock_mission.json"
        with open(self.mission_path, "w") as f:
            f.write("mission data")
            
        # Copy to AMU0
        with open(os.path.join(self.amu0_path, "phase3_reference_mission.json"), "w") as f:
            f.write("mission data")
            
        # Create pinned_context.json
        import json
        with open(os.path.join(self.amu0_path, "pinned_context.json"), "w") as f:
            json.dump({
                "rng_seed": 123, 
                "env_vars": {}, 
                "mock_time": "1000",
                "kernel_version": "mock",
                "cpu_microcode": "mock"
            }, f)

    def tearDown(self):
        import shutil
        if os.path.exists(self.amu0_path):
            shutil.rmtree(self.amu0_path)
        if os.path.exists(self.mission_path):
            os.remove(self.mission_path)
        # Reset initialization state
        init._initialized_amu0_path = None

    def test_replay_verification(self):
        self.fsm._RuntimeFSM__current_state = RuntimeState.GATES
        # self.fsm.transition_to(RuntimeState.REPLAY) # REPLAY state removed
        
        # Should pass if hashes match
        with patch("coo_runtime.util.context._verify_hardware_context"), \
             patch("coo_runtime.util.crypto.load_keys"), \
             patch("coo_runtime.runtime.init._verify_time_pinning"), \
             patch("coo_runtime.runtime.replay.run_pinned_subprocess") as mock_run, \
             patch("coo_runtime.runtime.replay.create_output_bundle", return_value=b"hash"):
            
            mock_run.return_value = MagicMock(stdout="output")
            self.replay.execute_replay(self.mission_path, self.amu0_path)

    def test_replay_mismatch(self):
        self.fsm._RuntimeFSM__current_state = RuntimeState.GATES
        # self.fsm.transition_to(RuntimeState.REPLAY) # REPLAY state removed
        
        # Modify mission
        with open(self.mission_path, "w") as f:
            f.write("modified data")
            
        with self.assertRaises(Exception) as cm:
            # We don't need to patch here because verify_reference_mission fails BEFORE initialize_runtime
            self.replay.execute_replay(self.mission_path, self.amu0_path)
        
        self.assertIn("Replay Mission Mismatch", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
