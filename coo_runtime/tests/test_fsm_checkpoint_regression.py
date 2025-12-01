import unittest
import os
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.util.crypto import load_keys

class TestFSMCheckpointRegression(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.amu0_path = os.path.join(self.test_dir, "amu0")
        os.makedirs(self.amu0_path)
        
        # Create pinned context
        with open(os.path.join(self.amu0_path, "pinned_context.json"), "w") as f:
            json.dump({"mock_time": "2025-01-01T00:00:00Z"}, f)
            
        # Mock keys for signing
        # We need real keys for signature verification to pass
        # Generate temp keys
        from nacl.signing import SigningKey
        self.sk = SigningKey.generate()
        self.vk = self.sk.verify_key
        
        # Patch crypto to use our keys
        self.patcher = patch("coo_runtime.util.crypto._CEO_PRIVATE_KEY", self.sk)
        self.patcher.start()
        self.patcher2 = patch("coo_runtime.util.crypto._CEO_PUBLIC_KEY", self.vk)
        self.patcher2.start()
        
        self.original_cwd = os.getcwd()
        self.fsm = RuntimeFSM()

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_checkpoint_restore(self):
        # Move FSM to allowed state
        # INIT -> AMENDMENT_PREP -> ... -> CAPTURE_AMU0
        # We can cheat by setting private var for test
        self.fsm._RuntimeFSM__current_state = RuntimeState.CAPTURE_AMU0
        self.fsm._history.append(RuntimeState.CAPTURE_AMU0)
        
        # Checkpoint
        os.chdir(self.test_dir) # Checkpoint writes to CWD
        self.fsm.checkpoint_state("test_ckpt", self.amu0_path)
        
        # Verify file exists
        self.assertTrue(os.path.exists("fsm_checkpoint_test_ckpt.json"))
        
        # Load
        new_fsm = RuntimeFSM()
        new_fsm.load_checkpoint("test_ckpt")
        
        # Verify
        self.assertEqual(new_fsm.current_state, RuntimeState.CAPTURE_AMU0)
        print("\nTestFSMCheckpointRegression: Checkpoint restored successfully.")

if __name__ == "__main__":
    unittest.main()
