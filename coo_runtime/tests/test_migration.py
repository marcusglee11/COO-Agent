import unittest
import os
import shutil
from coo_runtime.runtime.state_machine import RuntimeFSM, RuntimeState
from coo_runtime.runtime.migration import MigrationEngine
from coo_runtime.runtime.rollback import RollbackEngine

class TestMigration(unittest.TestCase):
    def setUp(self):
        self.fsm = RuntimeFSM()
        self.rollback = RollbackEngine(self.fsm)
        self.migration = MigrationEngine(self.fsm, self.rollback)
        
        # Setup mock directories
        self.pb_root = "mock_pb"
        self.coo_root = "mock_coo"
        os.makedirs(self.pb_root, exist_ok=True)
        with open(os.path.join(self.pb_root, "test_file.txt"), "w") as f:
            f.write("content")

    def tearDown(self):
        if os.path.exists(self.pb_root):
            shutil.rmtree(self.pb_root)
        if os.path.exists(self.coo_root):
            shutil.rmtree(self.coo_root)

    def test_migration_execution(self):
        # Force state
        self.fsm._current_state = RuntimeState.MIGRATION_SEQUENCE
        
        # Mock test runner
        test_runner = "echo 'Mock Test Runner'"
        
        # Execute
        self.migration.execute_migration(self.pb_root, self.coo_root, test_runner)
        
        # Verify coo_root populated
        self.assertTrue(os.path.exists(os.path.join(self.coo_root, "test_file.txt")))
        
        # Verify pb_root deleted (Step 6)
        self.assertFalse(os.path.exists(self.pb_root))

if __name__ == '__main__':
    unittest.main()
