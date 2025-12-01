import unittest
from unittest.mock import MagicMock, patch
import os
import sys
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState

class TestMigrationSnapshotB(unittest.TestCase):
    def setUp(self):
        self.fsm = MagicMock(spec=RuntimeFSM)
        self.rollback = MagicMock()
        self.engine = MigrationEngine(self.fsm, self.rollback)
        
    @patch("coo_runtime.runtime.migration.run_pinned_subprocess")
    @patch("coo_runtime.runtime.migration.initialize_runtime")
    @patch("coo_runtime.runtime.migration.amu0_utils.resolve_amu0_path")
    @patch("os.path.exists")
    @patch("shutil.rmtree")
    @patch("shutil.copy2")
    @patch("os.makedirs")
    @patch("os.walk")
    def test_snapshot_b_execution(self, mock_walk, mock_makedirs, mock_copy, mock_rmtree, mock_exists, mock_resolve, mock_init, mock_run_subprocess):
        # Setup
        mock_exists.return_value = True
        mock_walk.return_value = []
        mock_resolve.return_value = "/tmp/amu0"
        
        # Execute
        self.engine.execute_migration_phase_1("/pb", "/coo", "test_runner.py")
        
        # Verify
        # Check that run_pinned_subprocess was called twice
        # Once for Snapshot A (before delete)
        # Once for Snapshot B (after delete)
        self.assertEqual(mock_run_subprocess.call_count, 2)
        
        # Verify order: delete called before second test run?
        # We can check call args list
        # But verify delete was called
        mock_rmtree.assert_called_with("/pb")
        
        print("\nTestMigrationSnapshotB: Snapshot B executed successfully.")

if __name__ == "__main__":
    unittest.main()
