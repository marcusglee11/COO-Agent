import unittest
import os
import hashlib
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.replay import ReplayEngine

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

    def tearDown(self):
        import shutil
        if os.path.exists(self.amu0_path):
            shutil.rmtree(self.amu0_path)
        if os.path.exists(self.mission_path):
            os.remove(self.mission_path)

    def test_replay_verification(self):
        self.fsm._current_state = RuntimeState.GATES
        self.fsm.transition_to(RuntimeState.REPLAY)
        
        # Should pass if hashes match
        self.replay.execute_replay(self.mission_path, self.amu0_path)

    def test_replay_mismatch(self):
        self.fsm._current_state = RuntimeState.GATES
        self.fsm.transition_to(RuntimeState.REPLAY)
        
        # Modify mission
        with open(self.mission_path, "w") as f:
            f.write("modified data")
            
        with self.assertRaises(Exception) as cm:
            self.replay.execute_replay(self.mission_path, self.amu0_path)
        
        self.assertIn("Replay Mission Mismatch", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
