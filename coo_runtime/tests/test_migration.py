import unittest
import os
import shutil
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.runtime.rollback import RollbackEngine
from coo_runtime.runtime import init
from coo_runtime.runtime import init
from coo_runtime.util import amu0_utils
from unittest.mock import patch
import json

import tempfile
from unittest.mock import patch, MagicMock
import json
import sys

class TestMigration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # self.original_cwd = os.getcwd() # Removed
        # os.chdir(self.test_dir) # Removed
        
        self.fsm = RuntimeFSM()
        self.rollback = RollbackEngine(self.fsm)
        self.migration = MigrationEngine(self.fsm, self.rollback)
        
        # Setup mock directories
        self.pb_root = "mock_pb"
        self.coo_root = "mock_coo"
        os.makedirs(self.pb_root, exist_ok=True)
        with open(os.path.join(self.pb_root, "test_file.txt"), "w") as f:
            f.write("content")
            
        # Setup mock AMU0
        self.amu0_path = "mock_amu0_migration"
        os.makedirs(self.amu0_path, exist_ok=True)
        with open(os.path.join(self.amu0_path, "pinned_context.json"), "w") as f:
             json.dump({
                "rng_seed": 123, 
                "env_vars": {}, 
                "mock_time": "1000",
                "kernel_version": "mock",
                "cpu_microcode": "mock"
            }, f)
        
        # Create required AMU0 structure
        os.makedirs(os.path.join(self.amu0_path, "fs_snapshot"), exist_ok=True)
        with open(os.path.join(self.amu0_path, "snapshot_manifest.json"), "w") as f:
            json.dump({}, f)
        with open(os.path.join(self.amu0_path, "signature.sig"), "wb") as f:
            f.write(b"mock_bundle_sig")
            
        # Create rollback log
        with open(os.path.join(self.amu0_path, "rollback_log.jsonl"), "w") as f:
            pass
        with open(os.path.join(self.amu0_path, "rollback_log.sig"), "wb") as f:
            f.write(b"mock_log_sig")

        # Create active_amu0_path.json
        self.tracker_path = os.path.join(self.test_dir, "active_amu0_path.json")
        self.sig_path = os.path.join(self.test_dir, "active_amu0_path.json.sig")
        with open(self.tracker_path, "w") as f:
            json.dump({
                "amu0_path": self.amu0_path,
                "amu0_id": "mock_id",
                "created_at": "2025-01-01T00:00:00Z",
                "repo_commit": "mock_commit",
                "mode": "dev"
            }, f)
        with open(self.sig_path, "wb") as f:
            f.write(b"mock_sig")

        # Reset initialization state
        init._initialized_amu0_path = None
        
        # os.chdir(self.original_cwd) # Removed
        shutil.rmtree(self.test_dir)

    def test_migration_execution(self):
        # Force state
        self.fsm._RuntimeFSM__current_state = RuntimeState.MIGRATION_SEQUENCE
        
        # Mock test runner
        # Use sys.executable as it definitely exists and run_pinned_subprocess is patched
        test_runner_path = sys.executable
        
        # Execute
        with patch("coo_runtime.util.amu0_utils.resolve_amu0_path", return_value=self.amu0_path), \
             patch("coo_runtime.runtime.migration.amu0_utils.resolve_amu0_path", return_value=self.amu0_path), \
             patch("coo_runtime.runtime.rollback.amu0_utils.resolve_amu0_path", return_value=self.amu0_path), \
             patch("coo_runtime.util.context._verify_hardware_context"), \
             patch("coo_runtime.util.crypto.load_keys"), \
             patch("coo_runtime.runtime.init._verify_time_pinning"), \
             patch("coo_runtime.runtime.migration.run_pinned_subprocess"), \
             patch("coo_runtime.util.crypto.Signature.verify_data", return_value=True), \
             patch("coo_runtime.util.amu0_utils.derive_amu0_id", return_value="mock_id"), \
             patch("coo_runtime.runtime.rollback.RollbackEngine.execute_rollback") as mock_rollback:
            
            # Patch logger on the instance
            self.migration.logger = MagicMock()
            
            self.migration.execute_migration_phase_1(self.pb_root, self.coo_root, test_runner_path)
            
            # Verify rollback NOT called
            if mock_rollback.called:
                # Write error log to file
                with open("debug_error.txt", "w") as f:
                    f.write(f"DEBUG: Migration failed with: {self.migration.logger.error.call_args}")
            mock_rollback.assert_not_called()
        
        # Verify coo_root populated
        self.assertTrue(os.path.exists(os.path.join(self.coo_root, "test_file.txt")))
        
        # Verify pb_root deleted (Step 6)
        self.assertFalse(os.path.exists(self.pb_root))

if __name__ == '__main__':
    unittest.main()
